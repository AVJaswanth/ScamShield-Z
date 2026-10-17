"""
ScamShield Z: Risk Policy & Decision Engine
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

Features:
- 4 Risk Bands: Low, Medium, High, Very High
- Standard User Decisioning: ALLOW, ALLOW_WITH_NOTICE, CONFIRM, HOLD
- Vulnerable Customer Protection:
  - Escalates risk classification strictly by 1 band
  - Triggers "alert trusted contact" recommendation on Medium, High, and Very High bands
- Critical Value Escalation: Very High payments exceeding human_review_amount route to HUMAN_REVIEW
- Runtime Threshold Mutation & Validation with Restore Defaults capability
"""

from typing import Dict, Any


class PolicyEngine:
    DEFAULT_T_LOW = 0.05
    DEFAULT_T_MED = 0.35
    DEFAULT_T_HIGH = 0.65
    DEFAULT_HUMAN_REVIEW_AMOUNT = 5000.0

    def __init__(self, t_low: float = None, t_med: float = None, t_high: float = None, human_review_amount: float = None):
        self.t_low = t_low if t_low is not None else self.DEFAULT_T_LOW
        self.t_med = t_med if t_med is not None else self.DEFAULT_T_MED
        self.t_high = t_high if t_high is not None else self.DEFAULT_T_HIGH
        self.human_review_amount = human_review_amount if human_review_amount is not None else self.DEFAULT_HUMAN_REVIEW_AMOUNT
        self.validate_thresholds(self.t_low, self.t_med, self.t_high, self.human_review_amount)

    @staticmethod
    def validate_thresholds(t_low: float, t_med: float, t_high: float, human_review_amount: float):
        if not (0.0 < t_low < t_med < t_high < 1.0):
            raise ValueError(
                f"Invalid thresholds: Must satisfy 0 < t_low ({t_low}) < t_med ({t_med}) < t_high ({t_high}) < 1.0"
            )
        if human_review_amount <= 0:
            raise ValueError(f"human_review_amount must be positive: got {human_review_amount}")

    def update_thresholds(self, t_low: float, t_med: float, t_high: float, human_review_amount: float = None) -> Dict[str, Any]:
        hra = human_review_amount if human_review_amount is not None else self.human_review_amount
        self.validate_thresholds(t_low, t_med, t_high, hra)
        self.t_low = float(t_low)
        self.t_med = float(t_med)
        self.t_high = float(t_high)
        self.human_review_amount = float(hra)
        return self.get_thresholds()

    def restore_defaults(self) -> Dict[str, Any]:
        self.t_low = self.DEFAULT_T_LOW
        self.t_med = self.DEFAULT_T_MED
        self.t_high = self.DEFAULT_T_HIGH
        self.human_review_amount = self.DEFAULT_HUMAN_REVIEW_AMOUNT
        return self.get_thresholds()

    def get_thresholds(self) -> Dict[str, float]:
        return {
            "t_low": self.t_low,
            "t_med": self.t_med,
            "t_high": self.t_high,
            "human_review_amount": self.human_review_amount
        }

    def evaluate(self, score: float, amount: float, vulnerable_flag: int | bool) -> Dict[str, Any]:
        """
        Evaluate score and transaction context against real-time policy rules.
        """
        score = float(score)
        amount = float(amount)
        is_vulnerable = bool(vulnerable_flag)

        # Base risk band determination
        if score < self.t_low:
            raw_band = "LOW"
        elif score < self.t_med:
            raw_band = "MEDIUM"
        elif score < self.t_high:
            raw_band = "HIGH"
        else:
            raw_band = "VERY_HIGH"

        # Apply escalation for vulnerable users: strictly by one band
        band_escalation = {
            "LOW": "MEDIUM",
            "MEDIUM": "HIGH",
            "HIGH": "VERY_HIGH",
            "VERY_HIGH": "VERY_HIGH"
        }
        effective_band = band_escalation[raw_band] if is_vulnerable else raw_band

        # Standard Policy Actions
        # LOW -> ALLOW
        # MEDIUM -> ALLOW_WITH_NOTICE
        # HIGH -> CONFIRM
        # VERY_HIGH -> HOLD or HUMAN_REVIEW
        if effective_band == "LOW":
            decision = "ALLOW"
            action_label = "Payment Approved"
        elif effective_band == "MEDIUM":
            decision = "ALLOW_WITH_NOTICE"
            action_label = "Payment Approved with Security Notice"
        elif effective_band == "HIGH":
            decision = "CONFIRM"
            action_label = "Step-Up Confirmation Required"
        else: # VERY_HIGH
            if amount >= self.human_review_amount:
                decision = "HUMAN_REVIEW"
                action_label = "Held for Senior Fraud Analyst Review"
            else:
                decision = "HOLD"
                action_label = "Payment Temporarily Held"

        # Vulnerable contact alert flag
        alert_trusted_contact = is_vulnerable and (effective_band in ["MEDIUM", "HIGH", "VERY_HIGH"])

        return {
            "score": round(score, 4),
            "amount": amount,
            "raw_band": raw_band,
            "effective_band": effective_band,
            "is_vulnerable": is_vulnerable,
            "decision": decision,
            "action_label": action_label,
            "alert_trusted_contact": alert_trusted_contact,
            "thresholds_applied": self.get_thresholds()
        }
