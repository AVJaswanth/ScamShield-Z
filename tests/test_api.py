"""
Integration Tests: FastAPI Endpoints & Input Validation
IBM Z Datathon 2026: Real-Time AI for Critical Decisions
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.app import app

client = TestClient(app)


def test_get_state():
    res = client.get("/api/state")
    assert res.status_code == 200
    data = res.json()
    assert "stream_active" in data
    assert "scoring_backend" in data
    assert "thresholds" in data
    assert "kpi" in data
    assert data["synthetic_data"] is True


def test_manual_score_valid_payment():
    payload = {
        "amount": 250.0,
        "sender_id": "snd_unit_test",
        "payee_id": "pay_unit_test",
        "new_payee": False,
        "device_changed": False,
        "vulnerable": False
    }
    res = client.post("/api/score", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] in ["ALLOW", "ALLOW_WITH_NOTICE", "CONFIRM", "HOLD", "HUMAN_REVIEW"]
    assert "score" in data
    assert "primary_reason" in data
    assert "latency_ms" in data


def test_manual_score_invalid_amount():
    # Negative amount must be rejected by Pydantic validation (422)
    payload = {
        "amount": -50.0,
        "sender_id": "snd_bad",
        "payee_id": "pay_bad"
    }
    res = client.post("/api/score", json=payload)
    assert res.status_code == 422


def test_all_five_scenarios():
    scenarios = [
        "new_payee_large",
        "mule_fanin",
        "rapid_drain",
        "account_takeover",
        "normal_large_purchase"
    ]
    for scen in scenarios:
        res = client.post(f"/api/scenario/{scen}")
        assert res.status_code == 200, f"Scenario {scen} failed with {res.status_code}"
        data = res.json()
        assert data["scenario"] == scen
        assert "decision" in data
        assert "primary_reason" in data

    # Bad scenario name -> 400
    res_bad = client.post("/api/scenario/invalid_non_existent")
    assert res_bad.status_code == 400


def test_decision_actions():
    txn_id = "test_txn_dec_1"

    # 1. Confirm
    r_conf = client.post(f"/api/decision/{txn_id}", json={"action": "confirm"})
    assert r_conf.status_code == 200
    assert r_conf.json()["user_action"] == "CONFIRMED_BY_CUSTOMER"

    # 2. Cancel
    r_canc = client.post(f"/api/decision/{txn_id}", json={"action": "cancel"})
    assert r_canc.status_code == 200
    assert r_canc.json()["user_action"] == "CANCELLED_BY_CUSTOMER"

    # 3. Release
    r_rel = client.post(f"/api/decision/{txn_id}", json={"action": "release"})
    assert r_rel.status_code == 200
    assert r_rel.json()["user_action"] == "RELEASED_BY_FRAUD_TEAM"

    # 4. Keep Hold
    r_kh = client.post(f"/api/decision/{txn_id}", json={"action": "keep_hold"})
    assert r_kh.status_code == 200
    assert r_kh.json()["user_action"] == "HOLD_MAINTAINED"

    # 5. Invalid action -> 422
    r_inv = client.post(f"/api/decision/{txn_id}", json={"action": "invalid_action"})
    assert r_inv.status_code == 422


def test_stream_lifecycle():
    # Start
    r_start = client.post("/api/stream/start", json={"speed": 5.0})
    assert r_start.status_code == 200

    # Pause
    r_pause = client.post("/api/stream/pause")
    assert r_pause.status_code == 200

    # Reset
    r_reset = client.post("/api/stream/reset")
    assert r_reset.status_code == 200


def test_thresholds_endpoint():
    # Valid update
    r_up = client.post("/api/thresholds", json={"t_low": 0.08, "t_med": 0.38, "t_high": 0.68})
    assert r_up.status_code == 200
    assert r_up.json()["thresholds"]["t_low"] == 0.08

    # Invalid thresholds: t_low >= t_med -> 400
    r_bad = client.post("/api/thresholds", json={"t_low": 0.50, "t_med": 0.30, "t_high": 0.70})
    assert r_bad.status_code == 400

    # Restore defaults
    r_res = client.post("/api/thresholds", json={"action": "restore_defaults"})
    assert r_res.status_code == 200
    assert "thresholds" in r_res.json()


def test_backend_switch_validation():
    # WMLZ without endpoint must return 400 with explanation
    r = client.post("/api/backend", json={"backend": "WMLZ_HTTP", "wmlz_endpoint": ""})
    assert r.status_code == 400
    assert "unset" in r.json()["detail"].lower()


def test_audit_csv_export():
    res = client.get("/api/audit.csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "sender_id" in res.text
    assert "[SYNTHETIC DATA]" in res.text


def test_fairness_and_metrics_endpoints():
    r_fair = client.get("/api/fairness")
    assert r_fair.status_code == 200
    assert r_fair.json()["synthetic_data"] is True

    r_met = client.get("/api/metrics")
    assert r_met.status_code == 200
    assert "models" in r_met.json()

    r_lat = client.get("/api/latency")
    assert r_lat.status_code == 200
    assert "live_ring_buffer" in r_lat.json()
