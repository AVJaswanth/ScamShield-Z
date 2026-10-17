"""
ScamShield Z: Model Explainability Engine
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

Features:
- Extracts exact Tree SHAP / pred_contrib feature contributions from LightGBM booster
- For non-allow decisions, identifies top 3 positive risk contributors
- Maps contributors strictly to deterministic, rule-bounded human-readable sentence templates
- Zero free-form hallucinations or ungrounded generative text
- Optional generative rewrite hook (strictly OFF by default)
"""

import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import numpy as np
import lightgbm as lgb

from src.features import FEATURE_NAMES

TEMPLATE_TABLE = {
    "first_payment_to_payee": lambda feat_val: "You have never sent a payment to this recipient account before.",
    "payee_distinct_senders_24h": lambda feat_val: (
        f"This recipient account received transfers from {int(feat_val)} different people today."
        if feat_val >= 2 else "This recipient account is receiving money from multiple new senders."
    ),
    "amount_vs_sender_median_30d": lambda feat_val: f"Payment amount is {feat_val:.1f}x larger than your typical 30-day transfer size.",
    "amount_vs_sender_max_30d": lambda feat_val: "Transfer amount exceeds your 30-day historical maximum payment size.",
    "device_changed": lambda feat_val: "This transfer was initiated from an unrecognized device not previously used.",
    "sender_txn_count_10m": lambda feat_val: f"Rapid transfer burst detected: {int(feat_val)} payments initiated in the last 10 minutes.",
    "sender_txn_count_1h": lambda feat_val: f"Unusually high activity: {int(feat_val)} payments sent in the past hour.",
    "velocity_ratio_vs_baseline": lambda feat_val: f"Transaction velocity is {feat_val:.1f}x higher than your daily baseline pattern.",
    "is_round_amount": lambda feat_val: "The payment is a large round sum commonly associated with impersonation scams.",
    "payee_onward_share_1h": lambda feat_val: "Destination account exhibits sudden concentrated inflows characteristic of money mules.",
    "hour_of_day": lambda feat_val: f"Transaction submitted at high-risk hour ({int(feat_val):02d}:00).",
    "new_session": lambda feat_val: "Transfer requested immediately upon a newly opened session without prior browsing.",
    "payee_age_hours": lambda feat_val: "The recipient account was recently registered with limited operating history.",
    "vulnerable_flag": lambda feat_val: "Account has opt-in vulnerable customer protections enabled.",
    "account_age_days": lambda feat_val: "Account profile has limited tenure history.",
    "sender_txn_count_24h": lambda feat_val: f"Elevated cumulative 24-hour payment count ({int(feat_val)} transfers)."
}


class Explainer:
    def __init__(self, booster_path: str = None):
        if booster_path is None:
            booster_path = os.path.join(BASE_DIR, "models", "lgbm_booster.txt")
        self.booster_path = booster_path
        self.booster = None
        self._load_booster()

    def _load_booster(self):
        if os.path.exists(self.booster_path):
            self.booster = lgb.Booster(model_file=self.booster_path)

    def explain(
        self,
        feature_vector: list[float],
        decision: str,
        enable_generative_rewrite: bool = False
    ) -> dict:
        """
        Explain non-allow decisions using exact LightGBM tree contribution factors.
        For ALLOW decisions, returns standard approval rationale.
        """
        if decision == "ALLOW":
            return {
                "decision": decision,
                "primary_reason": "Payment pattern is fully consistent with established account history.",
                "top_factors": [],
                "generative_rewrite_applied": False
            }

        if self.booster is None:
            self._load_booster()
            if self.booster is None:
                return {
                    "decision": decision,
                    "primary_reason": "Elevated risk detected across transaction behavioral factors.",
                    "top_factors": [],
                    "generative_rewrite_applied": False
                }

        # Calculate exact tree contributions (SHAP values)
        X = np.array([feature_vector], dtype=np.float32)
        # pred_contrib returns array of shape (1, num_features + 1)
        contribs = self.booster.predict(X, pred_contrib=True)[0]
        # First 16 elements correspond to FEATURE_NAMES
        feat_contribs = contribs[:len(FEATURE_NAMES)]

        # Pair features with their contribution and value
        scored_factors = []
        for i, name in enumerate(FEATURE_NAMES):
            c_val = float(feat_contribs[i])
            f_val = float(feature_vector[i])
            if c_val > 0.0: # Positive contribution towards fraud
                scored_factors.append((name, c_val, f_val))

        # Sort descending by risk contribution
        scored_factors.sort(key=lambda x: x[1], reverse=True)
        top_3 = scored_factors[:3]

        reasons = []
        factor_details = []
        for name, c_val, f_val in top_3:
            template_fn = TEMPLATE_TABLE.get(name, lambda v: f"Unusual risk factor detected in {name}.")
            sentence = template_fn(f_val)
            reasons.append(sentence)
            factor_details.append({
                "feature": name,
                "contribution": round(c_val, 4),
                "value": round(f_val, 2),
                "explanation": sentence
            })

        if not reasons:
            primary_reason = "Transaction attributes exceed risk thresholds for this payment channel."
        else:
            primary_reason = reasons[0]

        # Optional Generative Rewrite Hook (OFF by default)
        if enable_generative_rewrite:
            primary_reason = self._generative_rewrite_hook(reasons, enabled=True)
            rewrite_applied = True
        else:
            rewrite_applied = False

        return {
            "decision": decision,
            "primary_reason": primary_reason,
            "reasons": reasons,
            "top_factors": factor_details,
            "generative_rewrite_applied": rewrite_applied
        }

    @staticmethod
    def _generative_rewrite_hook(reasons: list[str], enabled: bool = False) -> str:
        """
        Optional Generative AI hook for rephrasing explanations.
        Strictly OFF by default. When disabled, returns deterministic bullet text.
        """
        if not enabled or not reasons:
            return " ".join(reasons)
        # Bounded local formatting (no remote paid API calls)
        return f"Warning: {reasons[0]}"
