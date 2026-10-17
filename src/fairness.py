"""
ScamShield Z: Algorithmic Fairness & Disparate Impact Auditor
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

Features:
- Real-time and batch auditing of Hold Rate and False Positive Rate across demographics (age_group)
- Flags demographic disparities exceeding configurable tolerance limits
- Explicitly marks synthetic data provenance across all outputs
"""

import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from collections import defaultdict
import numpy as np
import pandas as pd
import yaml

from src.features import FeatureStore, compute_features, to_feature_vector
from src.scorer import ScoringEngine
from src.policy import PolicyEngine


class FairnessAuditor:
    def __init__(self, max_hold_rate_gap: float = 0.05):
        self.max_hold_rate_gap = max_hold_rate_gap
        # age_group -> statistics
        self.reset()

    def reset(self):
        self.groups = defaultdict(lambda: {
            "total": 0,
            "held": 0,
            "confirmed": 0,
            "allowed": 0,
            "actual_fraud": 0,
            "false_positives": 0
        })

    def record_decision(self, age_group: str, decision: str, is_fraud: int = 0):
        grp = self.groups[age_group]
        grp["total"] += 1
        if is_fraud:
            grp["actual_fraud"] += 1

        is_held = decision in ["HOLD", "HUMAN_REVIEW"]
        is_confirmed = decision == "CONFIRM"

        if is_held:
            grp["held"] += 1
            if not is_fraud:
                grp["false_positives"] += 1
        elif is_confirmed:
            grp["confirmed"] += 1
        else:
            grp["allowed"] += 1

    def get_audit_summary(self) -> dict:
        table = []
        hold_rates = []

        # Standard ordered groups
        order = ["18-34", "35-59", "60+"]
        all_keys = list(self.groups.keys())
        display_keys = [k for k in order if k in all_keys] + [k for k in all_keys if k not in order]

        for age_grp in display_keys:
            d = self.groups[age_grp]
            tot = d["total"]
            if tot > 0:
                h_rate = d["held"] / tot
                legit_count = tot - d["actual_fraud"]
                fpr = (d["false_positives"] / legit_count) if legit_count > 0 else 0.0
                hold_rates.append(h_rate)
            else:
                h_rate = 0.0
                fpr = 0.0

            table.append({
                "age_group": age_grp,
                "total_events": tot,
                "held_count": d["held"],
                "confirmed_count": d["confirmed"],
                "allowed_count": d["allowed"],
                "actual_fraud_count": d["actual_fraud"],
                "false_positives": d["false_positives"],
                "hold_rate": round(float(h_rate), 4),
                "fpr": round(float(fpr), 4)
            })

        if len(hold_rates) >= 2:
            gap = float(max(hold_rates) - min(hold_rates))
            disparity_alert = bool(gap > self.max_hold_rate_gap)
        else:
            gap = 0.0
            disparity_alert = False

        return {
            "synthetic_data": True,
            "data_label": "[SYNTHETIC DATA]",
            "max_configured_gap": self.max_hold_rate_gap,
            "observed_hold_rate_gap": round(gap, 4),
            "status": "DISPARITY_ALERT" if disparity_alert else "FAIR",
            "group_metrics": table
        }


def run_batch_fairness_audit(
    data_path: str = None,
    config_path: str = None
) -> dict:
    if data_path is None:
        data_path = os.path.join(BASE_DIR, "data", "synthetic_payments.csv")
    if config_path is None:
        config_path = os.path.join(BASE_DIR, "config.yaml")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    max_gap = cfg.get("fairness", {}).get("max_hold_rate_gap", 0.05)
    auditor = FairnessAuditor(max_hold_rate_gap=max_gap)
    store = FeatureStore()
    scorer = ScoringEngine()
    policy = PolicyEngine(
        t_low=cfg.get("policy", {}).get("t_low", 0.05),
        t_med=cfg.get("policy", {}).get("t_med", 0.35),
        t_high=cfg.get("policy", {}).get("t_high", 0.65),
        human_review_amount=cfg.get("policy", {}).get("human_review_amount", 5000.0)
    )

    print(f"Loading {data_path} for fairness evaluation...")
    df = pd.read_csv(data_path)

    print("Scoring transactions across demographic slices...")
    # Use test slice (last 30,000 transactions) for fair evaluation
    test_df = df.iloc[int(len(df) * 0.85):]

    for _, row in test_df.iterrows():
        ev = row.to_dict()
        feat_dict = compute_features(ev, store, update_store=True)
        vec = to_feature_vector(feat_dict)
        prob, _ = scorer.score(vec)
        pol = policy.evaluate(prob, ev["amount"], ev.get("vulnerable_flag", 0))
        auditor.record_decision(
            age_group=str(ev.get("age_group", "unknown")),
            decision=pol["decision"],
            is_fraud=int(ev.get("is_fraud", 0))
        )

    summary = auditor.get_audit_summary()
    print("\n--- FAIRNESS & DISPARATE IMPACT AUDIT REPORT [SYNTHETIC DATA] ---")
    print(f"Status: {summary['status']} (Observed Gap: {summary['observed_hold_rate_gap']:.4f} | Limit: {summary['max_configured_gap']})")
    for grp in summary["group_metrics"]:
        print(f"Age Group {grp['age_group']:6s} | Total: {grp['total_events']:,} | Held: {grp['held_count']} | Hold Rate: {grp['hold_rate']*100:.2f}% | FPR: {grp['fpr']*100:.2f}%")
    print("-----------------------------------------------------------------\n")
    return summary


if __name__ == "__main__":
    run_batch_fairness_audit()
