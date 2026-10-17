"""
Unit Tests: Model Explainability & Template Integrity
IBM Z Datathon 2026: Real-Time AI for Critical Decisions
"""

import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.explain import Explainer, TEMPLATE_TABLE
from src.features import FEATURE_NAMES


def test_explain_allow_decision():
    explainer = Explainer()
    vec = [0.0] * len(FEATURE_NAMES)
    res = explainer.explain(vec, decision="ALLOW")
    assert res["decision"] == "ALLOW"
    assert "consistent" in res["primary_reason"].lower()
    assert res["generative_rewrite_applied"] is False


def test_explain_non_allow_deterministic_templates():
    explainer = Explainer()
    # High risk feature vector: high velocity, first payment to payee, new device
    vec = [15.0] * len(FEATURE_NAMES)
    vec[FEATURE_NAMES.index("first_payment_to_payee")] = 1.0
    vec[FEATURE_NAMES.index("device_changed")] = 1.0
    vec[FEATURE_NAMES.index("payee_distinct_senders_24h")] = 25.0

    res = explainer.explain(vec, decision="HOLD", enable_generative_rewrite=False)
    assert res["decision"] == "HOLD"
    assert res["generative_rewrite_applied"] is False
    assert len(res["top_factors"]) <= 3

    # Verify that each explanation matches the template table exactly
    for factor in res["top_factors"]:
        feat_name = factor["feature"]
        assert feat_name in TEMPLATE_TABLE, f"Feature {feat_name} must have a registered template"
        template_fn = TEMPLATE_TABLE[feat_name]
        expected_sentence = template_fn(factor["value"])
        assert factor["explanation"] == expected_sentence, (
            f"Explanation '{factor['explanation']}' does not match template '{expected_sentence}'"
        )


def test_generative_rewrite_off_by_default():
    explainer = Explainer()
    vec = [5.0] * len(FEATURE_NAMES)
    res = explainer.explain(vec, decision="CONFIRM")
    assert res["generative_rewrite_applied"] is False
