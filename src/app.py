"""
ScamShield Z: Real-Time FastAPI Server & SSE Stream Engine
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

Features:
- Live Server-Sent Events (/api/events)
- Full Pydantic request validation and structured error handling
- Dynamic scenario injection (new_payee_large, mule_fanin, rapid_drain, account_takeover, normal_large_purchase)
- Interactive decision mutation (confirm, cancel, release, keep_hold)
- CSV Audit log export (/api/audit.csv)
- Offline & live latency metrics, model metrics, fairness auditor
- Static file serving for plain HTML/CSS/vanilla JS + local Chart.js
"""

import os
import sys
import time
import json
import uuid
import asyncio
from typing import Optional, Literal
from datetime import datetime, timezone
import yaml
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.features import FeatureStore, compute_features, to_feature_vector
from src.scorer import ScoringEngine
from src.policy import PolicyEngine
from src.explain import Explainer
from src.fairness import FairnessAuditor
from src.generate_data import tokenize

# Load configuration
config_path = os.path.join(BASE_DIR, "config.yaml")
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        APP_CONFIG = yaml.safe_load(f)
else:
    APP_CONFIG = {}

# Initialize Core Services
feature_store = FeatureStore()
scoring_engine = ScoringEngine(
    onnx_model_path=os.path.join(BASE_DIR, "models", "lgbm_scam.onnx"),
    backend=APP_CONFIG.get("backend", {}).get("active", "LOCAL_ONNX"),
    wmlz_endpoint=APP_CONFIG.get("backend", {}).get("wmlz_endpoint", "")
)
policy_cfg = APP_CONFIG.get("policy", {})
policy_engine = PolicyEngine(
    t_low=policy_cfg.get("t_low", 0.05),
    t_med=policy_cfg.get("t_med", 0.35),
    t_high=policy_cfg.get("t_high", 0.65),
    human_review_amount=policy_cfg.get("human_review_amount", 5000.0)
)
explainer = Explainer(booster_path=os.path.join(BASE_DIR, "models", "lgbm_booster.txt"))
fairness_auditor = FairnessAuditor(
    max_hold_rate_gap=APP_CONFIG.get("fairness", {}).get("max_hold_rate_gap", 0.05)
)

app = FastAPI(
    title="ScamShield Z",
    description="Real-Time AI Scam Payment Detection Demo (IBM Z Datathon 2026)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Global Stream & State Management
class AppState:
    def __init__(self):
        self.stream_active = False
        self.stream_speed = 1.0 # 1x, 5x, 20x
        self.stream_task: Optional[asyncio.Task] = None
        self.audit_log: list[dict] = []
        self.sse_queues: list[asyncio.Queue] = []
        self.kpi = {
            "events_scored": 0,
            "allowed_count": 0,
            "confirmed_count": 0,
            "held_count": 0,
            "human_review_count": 0
        }
        self.vulnerable_mode_global = False
        self.stream_index = 0
        self.test_events = []
        self._load_sample_data()

    def _load_sample_data(self):
        jsonl_path = os.path.join(BASE_DIR, "data", "test_payments.jsonl")
        if os.path.exists(jsonl_path):
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.test_events.append(json.loads(line))

state = AppState()


# Broadcast helper to all connected SSE clients
async def broadcast_event(event_data: dict):
    # Keep last 5,000 in memory audit
    state.audit_log.append(event_data)
    if len(state.audit_log) > 5000:
        state.audit_log.pop(0)

    # Dispatch to all open SSE connections
    dead_queues = []
    payload = json.dumps(event_data)
    for q in state.sse_queues:
        try:
            q.put_nowait(payload)
        except Exception:
            dead_queues.append(q)
    for dq in dead_queues:
        if dq in state.sse_queues:
            state.sse_queues.remove(dq)


def score_and_record_payment(
    payment: dict,
    user_override_vulnerable: Optional[bool] = None,
    scenario_tag: Optional[str] = None
) -> dict:
    """Core scoring pipeline executed for stream, manual scores, and scenarios."""
    txn_id = payment.get("id", f"txn_{uuid.uuid4().hex[:10]}")
    ts = payment.get("ts", datetime.now(timezone.utc).isoformat())
    sender_id = payment.get("sender_id", "snd_unknown")
    payee_id = payment.get("payee_id", "pay_unknown")
    amount = float(payment["amount"])
    device_id = payment.get("device_id", "dev_primary")

    # Vulnerability calculation
    is_vuln = bool(payment.get("vulnerable_flag", 0))
    if user_override_vulnerable is not None:
        is_vuln = user_override_vulnerable
    elif state.vulnerable_mode_global:
        is_vuln = True

    event_payload = {
        "ts": ts,
        "sender_id": sender_id,
        "payee_id": payee_id,
        "amount": amount,
        "device_id": device_id,
        "hour": payment.get("hour", datetime.now(timezone.utc).hour),
        "vulnerable_flag": 1 if is_vuln else 0,
        "account_age_days": payment.get("account_age_days", 180),
        "age_group": payment.get("age_group", "60+" if is_vuln else "35-59")
    }

    # 1. Unified Feature Extraction (rolling store)
    feat_dict = compute_features(event_payload, feature_store, update_store=True)
    vec = to_feature_vector(feat_dict)

    # 2. Model Inference
    prob, latency_ms = scoring_engine.score(vec)

    # 3. Policy Evaluation
    policy_res = policy_engine.evaluate(prob, amount, is_vuln)
    decision = policy_res["decision"]

    # 4. Explainability (Rule-bounded)
    explanation = explainer.explain(vec, decision)

    # 5. Fairness Audit Tracking
    fairness_auditor.record_decision(
        age_group=event_payload["age_group"],
        decision=decision,
        is_fraud=int(payment.get("is_fraud", 0))
    )

    # Update KPIs
    state.kpi["events_scored"] += 1
    if decision in ["ALLOW", "ALLOW_WITH_NOTICE"]:
        state.kpi["allowed_count"] += 1
    elif decision == "CONFIRM":
        state.kpi["confirmed_count"] += 1
    elif decision == "HOLD":
        state.kpi["held_count"] += 1
    elif decision == "HUMAN_REVIEW":
        state.kpi["human_review_count"] += 1

    decision_record = {
        "id": txn_id,
        "ts": ts,
        "sender_id": sender_id,
        "payee_id": payee_id,
        "amount": amount,
        "score": round(prob, 4),
        "raw_band": policy_res["raw_band"],
        "effective_band": policy_res["effective_band"],
        "decision": decision,
        "action_label": policy_res["action_label"],
        "alert_trusted_contact": policy_res["alert_trusted_contact"],
        "is_vulnerable": is_vuln,
        "age_group": event_payload["age_group"],
        "primary_reason": explanation["primary_reason"],
        "reasons": explanation.get("reasons", []),
        "top_factors": explanation.get("top_factors", []),
        "latency_ms": round(latency_ms, 3),
        "scoring_backend": scoring_engine.backend,
        "user_action": "PENDING" if decision in ["CONFIRM", "HOLD", "HUMAN_REVIEW"] else "AUTO_RESOLVED",
        "scenario": scenario_tag,
        "synthetic_data": True,
        "data_label": "[SYNTHETIC DATA]"
    }

    return decision_record


# Background Stream Task
async def stream_worker():
    print("Background payment stream worker started.")
    try:
        while state.stream_active:
            if not state.test_events:
                # Synthesize a fallback event if sample file was empty
                s_id = tokenize(f"snd_{uuid.uuid4().hex[:4]}", "salt", "snd")
                p_id = tokenize(f"pay_{uuid.uuid4().hex[:4]}", "salt", "pay")
                ev = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "sender_id": s_id,
                    "payee_id": p_id,
                    "amount": round(float(np.random.lognormal(3.5, 0.7)), 2),
                    "device_id": "dev_mobile",
                    "channel": "MOBILE_APP",
                    "age_group": "35-59",
                    "vulnerable_flag": 0,
                    "is_fraud": 0
                }
            else:
                ev = state.test_events[state.stream_index % len(state.test_events)]
                state.stream_index += 1

            record = score_and_record_payment(ev)
            await broadcast_event(record)

            # Sleep inversely proportional to speed
            delay = max(0.05, 1.0 / state.stream_speed)
            await asyncio.sleep(delay)
    except asyncio.CancelledError:
        print("Background payment stream worker stopped.")
    except Exception as e:
        print(f"Error in stream worker: {e}")


# --- Pydantic Request Models ---
class ManualScoreRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Payment transfer amount")
    sender_id: Optional[str] = Field("snd_manual_user", description="Sender token identifier")
    payee_id: Optional[str] = Field("pay_manual_recipient", description="Payee token identifier")
    new_payee: bool = Field(False, description="Whether this is first transfer to payee")
    device_changed: bool = Field(False, description="Whether transaction initiated from new device")
    vulnerable: bool = Field(False, description="Whether sender has vulnerable account flag active")
    hour: Optional[int] = Field(None, ge=0, le=23, description="Hour of day (0-23)")


class DecisionActionRequest(BaseModel):
    action: Literal["confirm", "cancel", "release", "keep_hold"] = Field(
        ...,
        description="Action to execute on pending transaction"
    )


class ThresholdsRequest(BaseModel):
    action: Optional[Literal["restore_defaults"]] = None
    t_low: Optional[float] = Field(None, gt=0, lt=1)
    t_med: Optional[float] = Field(None, gt=0, lt=1)
    t_high: Optional[float] = Field(None, gt=0, lt=1)
    human_review_amount: Optional[float] = Field(None, gt=0)


class SpeedRequest(BaseModel):
    speed: float = Field(..., ge=0.5, le=50.0)


class BackendRequest(BaseModel):
    backend: Literal["LOCAL_ONNX", "WMLZ_HTTP"]
    wmlz_endpoint: Optional[str] = None


class VulnerableToggleRequest(BaseModel):
    enabled: bool


# --- API Routes ---

@app.get("/api/state")
def get_state():
    lat = scoring_engine.get_latency_metrics()
    return {
        "stream_active": state.stream_active,
        "stream_speed": state.stream_speed,
        "scoring_backend": scoring_engine.backend,
        "wmlz_endpoint": scoring_engine.wmlz_endpoint,
        "wmlz_available": bool(scoring_engine.wmlz_endpoint.strip()),
        "vulnerable_mode_global": state.vulnerable_mode_global,
        "thresholds": policy_engine.get_thresholds(),
        "kpi": {
            **state.kpi,
            "p99_latency_ms": lat["p99_ms"]
        },
        "synthetic_data": True,
        "data_label": "[SYNTHETIC DATA]"
    }


@app.post("/api/stream/start")
async def start_stream(req: Optional[SpeedRequest] = None):
    if req and req.speed:
        state.stream_speed = float(req.speed)
    if not state.stream_active:
        state.stream_active = True
        state.stream_task = asyncio.create_task(stream_worker())
    return {"status": "started", "speed": state.stream_speed}


@app.post("/api/stream/pause")
async def pause_stream():
    state.stream_active = False
    if state.stream_task:
        state.stream_task.cancel()
        state.stream_task = None
    return {"status": "paused"}


@app.post("/api/stream/reset")
async def reset_stream():
    state.stream_active = False
    if state.stream_task:
        state.stream_task.cancel()
        state.stream_task = None

    state.stream_index = 0
    feature_store.reset()
    scoring_engine.latency_buffer.clear()
    fairness_auditor.reset()
    state.audit_log.clear()
    state.kpi = {
        "events_scored": 0,
        "allowed_count": 0,
        "confirmed_count": 0,
        "held_count": 0,
        "human_review_count": 0
    }
    return {"status": "reset_completed"}


@app.post("/api/stream/speed")
def set_speed(req: SpeedRequest):
    state.stream_speed = float(req.speed)
    return {"status": "speed_updated", "speed": state.stream_speed}


@app.post("/api/vulnerable-mode")
def toggle_vulnerable_mode(req: VulnerableToggleRequest):
    state.vulnerable_mode_global = req.enabled
    return {"status": "vulnerable_mode_updated", "enabled": state.vulnerable_mode_global}


@app.post("/api/score")
async def score_manual(req: ManualScoreRequest):
    # Prime feature store if simulating new payee or changed device
    current_t = time.time()
    s_id = req.sender_id or "snd_manual_user"
    p_id = req.payee_id or "pay_manual_recipient"

    if not req.new_payee:
        # Record prior historical transfer so it's NOT a first payment
        feature_store.record_event(current_t - 86400 * 5, s_id, p_id, 50.0, "dev_primary")

    dev_id = "dev_secondary_unknown" if req.device_changed else "dev_primary"
    if req.device_changed:
        # Establish prior device so change is flagged
        feature_store.record_event(current_t - 3600 * 2, s_id, "pay_utility", 45.0, "dev_primary")

    # Establish baseline median history for realistic ratio
    feature_store.record_event(current_t - 86400 * 3, s_id, "pay_grocery", 60.0, "dev_primary")

    payment = {
        "id": f"manual_{uuid.uuid4().hex[:8]}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "sender_id": s_id,
        "payee_id": p_id,
        "amount": float(req.amount),
        "device_id": dev_id,
        "hour": req.hour if req.hour is not None else datetime.now(timezone.utc).hour,
        "vulnerable_flag": 1 if req.vulnerable else 0,
        "age_group": "60+" if req.vulnerable else "35-59",
        "is_fraud": 0
    }

    record = score_and_record_payment(payment, user_override_vulnerable=req.vulnerable)
    await broadcast_event(record)
    return record


@app.post("/api/scenario/{name}")
async def inject_scenario(name: str):
    valid_scenarios = [
        "new_payee_large",
        "mule_fanin",
        "rapid_drain",
        "account_takeover",
        "normal_large_purchase"
    ]
    if name not in valid_scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario name: {name}. Must be one of {valid_scenarios}"
        )

    current_t = time.time()
    salt = "scenario_salt"
    now_iso = datetime.now(timezone.utc).isoformat()

    if name == "new_payee_large":
        # Elderly customer tricked into sending $4,500 round sum to never-before-seen payee
        s_id = tokenize("victim_senior_01", salt, "snd")
        p_id = tokenize(f"impersonator_{uuid.uuid4().hex[:4]}", salt, "pay")
        # History: modest $35 transactions
        feature_store.record_event(current_t - 86400 * 2, s_id, "pay_known_grocery", 35.0, "dev_phone")
        payment = {
            "id": f"scen_newpay_{uuid.uuid4().hex[:6]}",
            "ts": now_iso,
            "sender_id": s_id,
            "payee_id": p_id,
            "amount": 4500.0,
            "device_id": "dev_phone",
            "hour": 14,
            "age_group": "60+",
            "vulnerable_flag": 1,
            "is_fraud": 1
        }

    elif name == "mule_fanin":
        # Destination payee receiving payments from 18 distinct victims today
        mule_payee = tokenize("mule_syndicate_account", salt, "pay")
        for i in range(18):
            v_id = tokenize(f"victim_snd_{i}", salt, "snd")
            feature_store.record_event(current_t - (i * 1200 + 300), v_id, mule_payee, 450.0, "dev_v")

        s_id = tokenize("latest_victim_snd", salt, "snd")
        payment = {
            "id": f"scen_mule_{uuid.uuid4().hex[:6]}",
            "ts": now_iso,
            "sender_id": s_id,
            "payee_id": mule_payee,
            "amount": 1850.0,
            "device_id": "dev_app",
            "hour": 16,
            "age_group": "35-59",
            "vulnerable_flag": 0,
            "is_fraud": 1
        }

    elif name == "rapid_drain":
        # 5th transfer in 8 minutes draining funds
        s_id = tokenize("drained_user_99", salt, "snd")
        p_id = tokenize("crypto_cashout", salt, "pay")
        for step in range(4):
            feature_store.record_event(current_t - (240 - step * 50), s_id, p_id, 800.0, "dev_drain")

        payment = {
            "id": f"scen_drain_{uuid.uuid4().hex[:6]}",
            "ts": now_iso,
            "sender_id": s_id,
            "payee_id": p_id,
            "amount": 1200.0,
            "device_id": "dev_drain",
            "hour": 22,
            "age_group": "18-34",
            "vulnerable_flag": 0,
            "is_fraud": 1
        }

    elif name == "account_takeover":
        # New device login in middle of night (03:00) sending $5,200
        s_id = tokenize("ato_victim_44", salt, "snd")
        p_id = tokenize("offshore_exchange", salt, "pay")
        # Established user on dev_iphone
        feature_store.record_event(current_t - 86400 * 7, s_id, "pay_landlord", 950.0, "dev_iphone")
        payment = {
            "id": f"scen_ato_{uuid.uuid4().hex[:6]}",
            "ts": now_iso,
            "sender_id": s_id,
            "payee_id": p_id,
            "amount": 5200.0,
            "device_id": "dev_unrecognized_vpn_node",
            "hour": 3,
            "age_group": "35-59",
            "vulnerable_flag": 0,
            "is_fraud": 1
        }

    else: # normal_large_purchase
        # Honest hard case: $2,800 to recognized furniture store from primary device
        s_id = tokenize("honest_customer_12", salt, "snd")
        furniture_store = tokenize("trusted_home_furnishings", salt, "pay")
        feature_store.record_event(current_t - 86400 * 20, s_id, furniture_store, 250.0, "dev_laptop")
        feature_store.record_event(current_t - 86400 * 5, s_id, "pay_utility", 120.0, "dev_laptop")
        payment = {
            "id": f"scen_honest_{uuid.uuid4().hex[:6]}",
            "ts": now_iso,
            "sender_id": s_id,
            "payee_id": furniture_store,
            "amount": 2800.0,
            "device_id": "dev_laptop",
            "hour": 15,
            "age_group": "35-59",
            "vulnerable_flag": 0,
            "is_fraud": 0
        }

    record = score_and_record_payment(payment, scenario_tag=name)
    await broadcast_event(record)
    return record


@app.post("/api/decision/{decision_id}")
async def handle_user_decision(decision_id: str, req: DecisionActionRequest):
    # Find event in audit log
    found = None
    for item in reversed(state.audit_log):
        if item["id"] == decision_id:
            found = item
            break

    if not found:
        # Create virtual stub if not in recent memory
        found = {
            "id": decision_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "decision": "CONFIRM",
            "user_action": "PENDING"
        }
        state.audit_log.append(found)

    action_map = {
        "confirm": "CONFIRMED_BY_CUSTOMER",
        "cancel": "CANCELLED_BY_CUSTOMER",
        "release": "RELEASED_BY_FRAUD_TEAM",
        "keep_hold": "HOLD_MAINTAINED"
    }

    new_action = action_map[req.action]
    found["user_action"] = new_action

    # Update event for broadcast
    update_event = {
        "type": "DECISION_UPDATE",
        "id": decision_id,
        "user_action": new_action,
        "action_timestamp": datetime.now(timezone.utc).isoformat()
    }
    await broadcast_event(update_event)
    return {"id": decision_id, "user_action": new_action, "status": "updated"}


@app.post("/api/thresholds")
def update_thresholds(req: ThresholdsRequest):
    if req.action == "restore_defaults":
        res = policy_engine.restore_defaults()
        return {"status": "defaults_restored", "thresholds": res}

    if req.t_low is None or req.t_med is None or req.t_high is None:
        raise HTTPException(
            status_code=422,
            detail="t_low, t_med, and t_high are required to update thresholds."
        )

    try:
        res = policy_engine.update_thresholds(
            t_low=req.t_low,
            t_med=req.t_med,
            t_high=req.t_high,
            human_review_amount=req.human_review_amount
        )
        return {"status": "thresholds_updated", "thresholds": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/backend")
def set_backend(req: BackendRequest):
    try:
        scoring_engine.set_backend(req.backend, req.wmlz_endpoint)
        return {
            "status": "backend_updated",
            "backend": scoring_engine.backend,
            "wmlz_endpoint": scoring_engine.wmlz_endpoint
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/fairness")
def get_fairness():
    return fairness_auditor.get_audit_summary()


@app.get("/api/metrics")
def get_metrics():
    metrics_path = os.path.join(BASE_DIR, "reports", "metrics.json")
    if os.path.exists(metrics_path):
        with open(metrics_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "status": "not measured",
        "detail": "Run 'make train' or 'python src/train.py' to generate metrics."
    }


@app.get("/api/latency")
def get_latency():
    live_stats = scoring_engine.get_latency_metrics()
    replay_path = os.path.join(BASE_DIR, "reports", "latency.json")
    replay_stats = "not measured"
    if os.path.exists(replay_path):
        try:
            with open(replay_path, "r", encoding="utf-8") as f:
                replay_stats = json.load(f)
        except Exception:
            pass

    return {
        "live_ring_buffer": live_stats,
        "offline_100k_replay": replay_stats,
        "scoring_backend": scoring_engine.backend,
        "synthetic_data": True,
        "data_label": "[SYNTHETIC DATA]"
    }


@app.get("/api/audit.csv")
def download_audit_csv():
    """Export formatted CSV of audit log records."""
    headers = [
        "id", "ts", "sender_id", "payee_id", "amount", "score",
        "raw_band", "effective_band", "decision", "action_label",
        "is_vulnerable", "age_group", "primary_reason", "user_action",
        "scoring_backend", "is_synthetic"
    ]
    lines = [
        "# PROVENANCE: [SYNTHETIC DATA] - IBM Z Datathon 2026",
        ",".join(headers)
    ]

    for row in state.audit_log:
        if row.get("type") == "DECISION_UPDATE":
            continue
        vals = [
            str(row.get("id", "")),
            str(row.get("ts", "")),
            str(row.get("sender_id", "")),
            str(row.get("payee_id", "")),
            f"{row.get('amount', 0.0):.2f}",
            f"{row.get('score', 0.0):.4f}",
            str(row.get("raw_band", "")),
            str(row.get("effective_band", "")),
            str(row.get("decision", "")),
            f"\"{row.get('action_label', '')}\"",
            str(row.get("is_vulnerable", False)),
            str(row.get("age_group", "")),
            f"\"{row.get('primary_reason', '').replace('\"', '\"\"')}\"",
            str(row.get("user_action", "")),
            str(row.get("scoring_backend", "LOCAL_ONNX")),
            "[SYNTHETIC DATA]"
        ]
        lines.append(",".join(vals))

    content = "\n".join(lines)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scamshield_audit_log.csv"}
    )


@app.get("/api/events")
async def events_sse(request: Request):
    """Server-Sent Events stream for live payment decisions."""
    client_queue = asyncio.Queue()
    state.sse_queues.append(client_queue)

    async def event_generator():
        try:
            # Send initial keep-alive ping
            yield "event: ping\ndata: {\"status\": \"connected\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(client_queue.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield "event: ping\ndata: {}\n\n"
        finally:
            if client_queue in state.sse_queues:
                state.sse_queues.remove(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# Mount static files at root
static_dir = os.path.join(BASE_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=False)
