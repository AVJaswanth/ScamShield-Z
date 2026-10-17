"""
Unit Tests: Risk Policy & Decision Rules
IBM Z Datathon 2026: Real-Time AI for Critical Decisions
"""

import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.policy import PolicyEngine


def test_standard_policy_bands():
    policy = PolicyEngine(t_low=0.10, t_med=0.40, t_high=0.70, human_review_amount=5000.0)

    # Low risk -> ALLOW
    res_low = policy.evaluate(score=0.05, amount=100.0, vulnerable_flag=0)
    assert res_low["decision"] == "ALLOW"
    assert res_low["raw_band"] == "LOW"
    assert res_low["alert_trusted_contact"] is False

    # Medium risk -> ALLOW_WITH_NOTICE
    res_med = policy.evaluate(score=0.25, amount=100.0, vulnerable_flag=0)
    assert res_med["decision"] == "ALLOW_WITH_NOTICE"
    assert res_med["raw_band"] == "MEDIUM"

    # High risk -> CONFIRM
    res_high = policy.evaluate(score=0.55, amount=100.0, vulnerable_flag=0)
    assert res_high["decision"] == "CONFIRM"
    assert res_high["raw_band"] == "HIGH"

    # Very High risk (< $5,000) -> HOLD
    res_vh = policy.evaluate(score=0.85, amount=2500.0, vulnerable_flag=0)
    assert res_vh["decision"] == "HOLD"
    assert res_vh["raw_band"] == "VERY_HIGH"

    # Very High risk (>= $5,000) -> HUMAN_REVIEW
    res_hr = policy.evaluate(score=0.85, amount=6000.0, vulnerable_flag=0)
    assert res_hr["decision"] == "HUMAN_REVIEW"
    assert res_hr["raw_band"] == "VERY_HIGH"


def test_vulnerable_customer_escalation():
    policy = PolicyEngine(t_low=0.10, t_med=0.40, t_high=0.70, human_review_amount=5000.0)

    # Raw Low (score 0.05) -> Escalated to MEDIUM -> ALLOW_WITH_NOTICE
    res_low_vuln = policy.evaluate(score=0.05, amount=100.0, vulnerable_flag=1)
    assert res_low_vuln["raw_band"] == "LOW"
    assert res_low_vuln["effective_band"] == "MEDIUM"
    assert res_low_vuln["decision"] == "ALLOW_WITH_NOTICE"
    assert res_low_vuln["alert_trusted_contact"] is True

    # Raw Medium (score 0.25) -> Escalated to HIGH -> CONFIRM + trusted contact alert
    res_med_vuln = policy.evaluate(score=0.25, amount=100.0, vulnerable_flag=1)
    assert res_med_vuln["raw_band"] == "MEDIUM"
    assert res_med_vuln["effective_band"] == "HIGH"
    assert res_med_vuln["decision"] == "CONFIRM"
    assert res_med_vuln["alert_trusted_contact"] is True

    # Raw High (score 0.55) -> Escalated to VERY_HIGH -> HOLD + trusted contact alert
    res_high_vuln = policy.evaluate(score=0.55, amount=100.0, vulnerable_flag=1)
    assert res_high_vuln["raw_band"] == "HIGH"
    assert res_high_vuln["effective_band"] == "VERY_HIGH"
    assert res_high_vuln["decision"] == "HOLD"
    assert res_high_vuln["alert_trusted_contact"] is True


def test_threshold_validation_and_mutation():
    policy = PolicyEngine()

    # Valid mutation
    updated = policy.update_thresholds(t_low=0.08, t_med=0.30, t_high=0.60, human_review_amount=4000.0)
    assert updated["t_low"] == 0.08
    assert updated["t_med"] == 0.30
    assert updated["t_high"] == 0.60
    assert updated["human_review_amount"] == 4000.0

    # Invalid: t_low >= t_med
    with pytest.raises(ValueError):
        policy.update_thresholds(t_low=0.45, t_med=0.40, t_high=0.70)

    # Invalid: t_med >= t_high
    with pytest.raises(ValueError):
        policy.update_thresholds(t_low=0.10, t_med=0.80, t_high=0.70)

    # Invalid: negative amount
    with pytest.raises(ValueError):
        policy.update_thresholds(t_low=0.10, t_med=0.40, t_high=0.70, human_review_amount=-50.0)

    # Restore defaults
    restored = policy.restore_defaults()
    assert restored["t_low"] == policy.DEFAULT_T_LOW
    assert restored["t_med"] == policy.DEFAULT_T_MED
    assert restored["t_high"] == policy.DEFAULT_T_HIGH
