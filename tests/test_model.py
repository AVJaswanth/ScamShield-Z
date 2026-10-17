"""
Unit Tests: ONNX Model Parity & Numerical Accuracy
IBM Z Datathon 2026: Real-Time AI for Critical Decisions
"""

import os
import sys
import json
import numpy as np
import lightgbm as lgb
import onnxruntime as ort
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.scorer import ScoringEngine


def test_onnx_model_file_exists():
    onnx_path = os.path.join(BASE_DIR, "models", "lgbm_scam.onnx")
    booster_path = os.path.join(BASE_DIR, "models", "lgbm_booster.txt")
    assert os.path.exists(onnx_path), "ONNX model file must exist in models/"
    assert os.path.exists(booster_path), "Booster model file must exist in models/"


def test_onnx_vs_lightgbm_parity_1000_samples():
    """Verify that ONNX runtime output matches native LightGBM within 1e-5 on 1,000 rows."""
    onnx_path = os.path.join(BASE_DIR, "models", "lgbm_scam.onnx")
    booster_path = os.path.join(BASE_DIR, "models", "lgbm_booster.txt")

    booster = lgb.Booster(model_file=booster_path)
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    np.random.seed(42)
    # Generate 1,000 diverse test feature vectors with 16 features
    test_X = np.random.uniform(0.0, 10.0, size=(1000, 16)).astype(np.float32)

    # Native LightGBM predictions
    lgb_preds = booster.predict(test_X)

    # ONNX Runtime predictions
    onnx_raw = session.run(None, {input_name: test_X})
    if len(onnx_raw) > 1:
        probs = onnx_raw[1]
        if isinstance(probs, list) and isinstance(probs[0], dict):
            onnx_preds = np.array([p[1] for p in probs], dtype=np.float32)
        elif isinstance(probs, np.ndarray):
            onnx_preds = probs[:, 1]
        else:
            onnx_preds = np.array(probs, dtype=np.float32)
    else:
        onnx_preds = onnx_raw[0][:, 1]

    diffs = np.abs(onnx_preds - lgb_preds)
    max_diff = float(np.max(diffs))

    print(f"Max difference on 1,000 random vectors: {max_diff:.8e}")
    assert max_diff < 1e-5, f"ONNX parity violation! Max difference {max_diff} >= 1e-5"


def test_scorer_ring_buffer_latency():
    scorer = ScoringEngine()
    dummy_vec = [1.0] * 16

    # Score 50 times
    for _ in range(50):
        prob, lat = scorer.score(dummy_vec)
        assert 0.0 <= prob <= 1.0
        assert lat > 0.0

    stats = scorer.get_latency_metrics()
    assert stats["sample_count"] == 50
    assert isinstance(stats["p50_ms"], float)
    assert isinstance(stats["p95_ms"], float)
    assert isinstance(stats["p99_ms"], float)
    assert stats["p50_ms"] <= stats["p95_ms"] <= stats["p99_ms"]


def test_metrics_json_integrity():
    metrics_path = os.path.join(BASE_DIR, "reports", "metrics.json")
    assert os.path.exists(metrics_path), "reports/metrics.json must exist"

    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    assert metrics["synthetic_data"] is True
    assert "[SYNTHETIC DATA]" in metrics["data_label"]
    assert "models" in metrics
    assert "lightgbm_production" in metrics["models"]
    assert metrics["models"]["lightgbm_production"]["onnx_parity_passed"] is True
    assert metrics["models"]["lightgbm_production"]["pr_auc"] > 0.80
    assert metrics["models"]["lightgbm_production"]["roc_auc"] > 0.90
