"""
ScamShield Z: Real-Time Scoring Engine
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

Features:
- Dual Backend: LOCAL_ONNX (default) or WMLZ_HTTP (IBM Watson Machine Learning for z/OS)
- Monotonic high-resolution timer recording per-call inference latency in a ring buffer
- Exposes p50, p95, and p99 real-time latency statistics
- Zero fake metrics: reports "not measured" if ring buffer is empty
"""

import os
import sys
import time
from collections import deque
import numpy as np
import onnxruntime as ort
import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class LatencyRingBuffer:
    """Fixed-capacity ring buffer tracking inference latencies in milliseconds."""
    def __init__(self, capacity: int = 2000):
        self.buffer = deque(maxlen=capacity)

    def record(self, latency_ms: float):
        self.buffer.append(latency_ms)

    def get_stats(self) -> dict:
        if not self.buffer:
            return {
                "p50_ms": "not measured",
                "p95_ms": "not measured",
                "p99_ms": "not measured",
                "mean_ms": "not measured",
                "sample_count": 0
            }
        arr = np.array(self.buffer, dtype=np.float64)
        return {
            "p50_ms": round(float(np.percentile(arr, 50)), 3),
            "p95_ms": round(float(np.percentile(arr, 95)), 3),
            "p99_ms": round(float(np.percentile(arr, 99)), 3),
            "mean_ms": round(float(np.mean(arr)), 3),
            "sample_count": len(self.buffer)
        }

    def clear(self):
        self.buffer.clear()


class ScoringEngine:
    def __init__(self, onnx_model_path: str = None, backend: str = "LOCAL_ONNX", wmlz_endpoint: str = ""):
        if onnx_model_path is None:
            onnx_model_path = os.path.join(BASE_DIR, "models", "lgbm_scam.onnx")
        self.onnx_model_path = onnx_model_path
        self.backend = backend
        self.wmlz_endpoint = wmlz_endpoint
        self.latency_buffer = LatencyRingBuffer()

        # Initialize ONNX Runtime session
        self.session = None
        self.input_name = None
        self._init_onnx()

    def _init_onnx(self):
        if os.path.exists(self.onnx_model_path):
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(
                self.onnx_model_path,
                sess_options=opts,
                providers=["CPUExecutionProvider"]
            )
            self.input_name = self.session.get_inputs()[0].name
        else:
            self.session = None

    def set_backend(self, backend: str, wmlz_endpoint: str = None) -> bool:
        if backend == "WMLZ_HTTP":
            ep = wmlz_endpoint if wmlz_endpoint is not None else self.wmlz_endpoint
            if not ep or not ep.strip():
                raise ValueError("WMLZ_HTTP backend cannot be activated: endpoint URL is unset.")
            self.wmlz_endpoint = ep.strip()
            self.backend = "WMLZ_HTTP"
            return True
        elif backend == "LOCAL_ONNX":
            if self.session is None:
                self._init_onnx()
            self.backend = "LOCAL_ONNX"
            return True
        else:
            raise ValueError(f"Unknown scoring backend: {backend}")

    def score(self, feature_vector: list[float]) -> tuple[float, float]:
        """
        Score a single transaction feature vector.
        Returns:
            (fraud_probability: float, latency_ms: float)
        """
        t0 = time.perf_counter()

        if self.backend == "LOCAL_ONNX":
            if self.session is None:
                self._init_onnx()
                if self.session is None:
                    raise RuntimeError("ONNX model file not found. Run training first.")

            # Prepare 1x16 float32 tensor
            arr = np.array([feature_vector], dtype=np.float32)
            outputs = self.session.run(None, {self.input_name: arr})

            # Extract probability of class 1 (Fraud)
            if len(outputs) > 1:
                probs_out = outputs[1]
                if isinstance(probs_out, list) and isinstance(probs_out[0], dict):
                    prob = float(probs_out[0].get(1, 0.0))
                elif isinstance(probs_out, np.ndarray):
                    prob = float(probs_out[0, 1])
                else:
                    prob = float(probs_out[0])
            else:
                prob = float(outputs[0][0, 1])

        elif self.backend == "WMLZ_HTTP":
            if not self.wmlz_endpoint:
                raise RuntimeError("WMLZ_HTTP endpoint is not configured.")
            payload = {"inputs": [feature_vector]}
            resp = requests.post(self.wmlz_endpoint, json=payload, timeout=2.0)
            resp.raise_for_status()
            data = resp.json()
            prob = float(data["predictions"][0]["probability"])
        else:
            raise ValueError(f"Invalid backend: {self.backend}")

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.latency_buffer.record(elapsed_ms)
        return prob, elapsed_ms

    def get_latency_metrics(self) -> dict:
        return self.latency_buffer.get_stats()
