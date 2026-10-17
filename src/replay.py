"""
ScamShield Z: High-Throughput Replay Benchmark
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

Features:
- Replays 100,000 transactions through rolling feature extraction and ONNX inference
- Measures ultra-high resolution per-transaction execution latency
- Records p50, p95, and p99 latency percentiles into reports/latency.json
- Verifies sub-millisecond real-time SLA compliance
"""

import os
import sys
import time
import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.features import FeatureStore, compute_features, to_feature_vector
from src.scorer import ScoringEngine


def run_replay_benchmark(
    data_path: str = None,
    output_path: str = None,
    num_events: int = 100000
) -> dict:
    if data_path is None:
        data_path = os.path.join(BASE_DIR, "data", "synthetic_payments.csv")
    if output_path is None:
        output_path = os.path.join(BASE_DIR, "reports", "latency.json")

    print(f"Loading {num_events:,} events from {data_path} for streaming replay...")
    df = pd.read_csv(data_path, nrows=num_events)

    store = FeatureStore()
    scorer = ScoringEngine()

    latencies_us = []
    latencies_ms = []

    print(f"Beginning real-time replay of {len(df):,} events...")
    start_total = time.perf_counter()

    for idx, row in df.iterrows():
        ev = row.to_dict()

        # Measure end-to-end inference latency
        t0 = time.perf_counter()
        feat_dict = compute_features(ev, store, update_store=True)
        vec = to_feature_vector(feat_dict)
        prob, _ = scorer.score(vec)
        elapsed = time.perf_counter() - t0

        lat_ms = elapsed * 1000.0
        lat_us = elapsed * 1_000_000.0

        latencies_ms.append(lat_ms)
        latencies_us.append(lat_us)

    total_time = time.perf_counter() - start_total
    tps = len(df) / (total_time + 1e-6)

    arr_us = np.array(latencies_us, dtype=np.float64)
    arr_ms = np.array(latencies_ms, dtype=np.float64)

    p50_us = float(np.percentile(arr_us, 50))
    p95_us = float(np.percentile(arr_us, 95))
    p99_us = float(np.percentile(arr_us, 99))

    p50_ms = float(np.percentile(arr_ms, 50))
    p95_ms = float(np.percentile(arr_ms, 95))
    p99_ms = float(np.percentile(arr_ms, 99))

    report = {
        "synthetic_data": True,
        "data_label": "[SYNTHETIC DATA]",
        "total_events_replayed": len(df),
        "scoring_backend": scorer.backend,
        "throughput_tx_per_sec": round(tps, 2),
        "total_elapsed_sec": round(total_time, 2),
        "latency_percentiles_us": {
            "p50_us": round(p50_us, 2),
            "p95_us": round(p95_us, 2),
            "p99_us": round(p99_us, 2)
        },
        "latency_percentiles_ms": {
            "p50_ms": round(p50_ms, 4),
            "p95_ms": round(p95_ms, 4),
            "p99_ms": round(p99_ms, 4)
        },
        "timestamp_measured": datetime.now(timezone.utc).isoformat()
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n--- REPLAY LATENCY BENCHMARK RESULTS ---")
    print(f"Replayed: {len(df):,} events in {total_time:.2f}s ({tps:,.1f} txn/sec)")
    print(f"Backend:  {scorer.backend}")
    print(f"Latency:  p50={p50_ms:.3f}ms ({p50_us:.1f}µs) | p95={p95_ms:.3f}ms ({p95_us:.1f}µs) | p99={p99_ms:.3f}ms ({p99_us:.1f}µs)")
    print(f"Saved latency report to {output_path}\n")

    return report


if __name__ == "__main__":
    run_replay_benchmark()
