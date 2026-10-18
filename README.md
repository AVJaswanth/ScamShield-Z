# ScamShield Z — Real-Time AI for Critical Decisions

> **IBM Z Datathon 2026 Submission**  
> *Theme: Real-Time AI for Critical Decisions*

---

## 1. What It Is

**ScamShield Z** is a real-time scam and authorized push payment (APP) fraud detection and decisioning engine. It intercepts payments at sub-millisecond latency (sub-0.50ms p99, measured 0.492ms) and executes real-time AI scoring, 4-tier risk policy enforcement, rule-bounded explainability, and demographic fairness audits.

In modern banking, Authorized Push Payment (APP) scams trick legitimate account owners into sending money to fraudsters. Traditional rule engines and post-transaction batch analytics are too slow: once funds leave the bank via immediate payment rails, recovery is near impossible. ScamShield Z brings low-latency AI inference directly into the transactional path to intervene *before* funds are disbursed.

---

## 2. One-Command Quickstart

ScamShield Z runs locally on a standard laptop with zero paid APIs, zero cloud credentials, and no Kaggle login required.

### Clone and Run Everything:
```bash
# Navigate to the scamshield directory
cd scamshield

# Run complete pipeline: data generation, training, parity check, latency benchmark, unit tests, and E2E verification
make all
```

*(On Windows, `make.bat all` or `.\make.bat all` runs the exact same automated pipeline).*

### Launch the Live Interactive UI:
```bash
make run
```
Open your browser to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 3. Honest "What Ran Where" Table

| Component | Target Production Architecture (IBM Z) | What Ran in this Demo (Local Laptop) | Real Metric / Verification |
| :--- | :--- | :--- | :--- |
| **Scoring Engine** | IBM z16 Integrated On-Chip AI Accelerator (Telum processor) via WML for z/OS | Local CPU execution via ONNX Runtime session (`LOCAL_ONNX`) | p50 = 0.105 ms, p99 = 0.492 ms (4,890.1 txn/sec over 100,000 transactions) |
| **Model Parity** | Quantized compiler execution on z16 Telum NNPA hardware | Exported ONNX Open Neural Network Exchange graph | Max difference between native model & ONNX: **5.93e-08** (tolerance < 1e-05) |
| **Feature Store** | In-memory transactional state store on z/OS | In-memory bounded deque store (`src/features.py`) | Zero future leakage ($t_i$ computed strictly from events $< t_i$) |
| **Backend Switching** | REST adapter targeting WMLz endpoint (`WMLZ_HTTP`) | Fallback adapter with auto-disabled toggle and explanatory tooltip when URL is unset | Verified in E2E suite |
| **Dataset** | High-volume production core banking telemetry | Seeded synthetic stream of 200,000 events over 30 days (`[SYNTHETIC DATA]`) | Labeled everywhere as synthetic; reproducible via seed 42 |

---

## 4. Architecture Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                      SCAMSHIELD Z ARCHITECTURE                                      |
+----------------------------------------------------------------------------------------------------+

  [ Payment Transaction Rail ]
             │ (Amount, Sender, Payee, Device, Channel, Timestamp)
             ▼
  [ Real-Time Feature Store (src/features.py) ]
    ├── Per-entity rolling deques (bounded 30-day window)
    ├── Strict chronological isolation: zero future-leakage
    └── 16 Behavioral Features (velocity, mule fan-in, account depletion, new device)
             │
             ▼
  [ Dual AI Scoring Engine (src/scorer.py) ]
    ├── LOCAL_ONNX (Laptop CPU Runtime) ─────────► Measured p99: 0.492 ms
    └── WMLZ_HTTP (IBM Watson ML for z/OS) ──────► On-chip Telum AI Accelerator
             │
             ▼
  [ Risk Policy & Escalation Engine (src/policy.py) ]
    ├── Low Risk (< 0.05)         ──► ALLOW (Frictionless)
    ├── Medium Risk [0.05, 0.35)  ──► ALLOW_WITH_NOTICE (Standard) / CONFIRM (Vulnerable)
    ├── High Risk [0.35, 0.65)    ──► CONFIRM (Step-Up 2FA) / HOLD (Vulnerable)
    └── Very High Risk (>= 0.65)  ──► HOLD (or HUMAN_REVIEW if Amount >= $5,000)
             │
             ├──► [ Rule-Bounded Explainer (src/explain.py) ]
             │      └── LightGBM pred_contrib Tree SHAP -> Top 3 positive factors -> Fixed Templates
             │
             ├──► [ Fairness & Disparate Impact Auditor (src/fairness.py) ]
             │      └── Hold rate and False Positive Rate sliced across age demographics
             │
             ▼
  [ Server-Sent Events (SSE) Live Feed & Accessible Web UI (static/) ]
```

---

## 5. Measured Model Evaluation Metrics

*All metrics below are copied verbatim from [`reports/metrics.json`](reports/metrics.json), produced by running `src/train.py` on the strict 70/15/15 chronological split of the 200,000 synthetic payment stream and the external ULB Credit Card fraud benchmark (`data/external/creditcard.csv`).*

```json
{
  "synthetic_data": true,
  "data_label": "[SYNTHETIC DATA]",
  "synthetic_data_disclaimer": "Metrics on synthetic_payments.csv reflect clean separation of the planted fraud patterns (demonstrating feature extraction & ONNX pipeline integrity). They do not represent real-world deployment accuracy on noisy bank data. See external_benchmarks (ULB Credit Card) for real-world baseline.",
  "total_events": 200000,
  "splits": {
    "train_events": 140000,
    "val_events": 30000,
    "test_events": 30000,
    "test_fraud_count": 60
  },
  "models": {
    "baseline_logistic_regression": {
      "pr_auc": 0.8636,
      "roc_auc": 0.9992,
      "recall_at_1pct_fpr": 0.9833
    },
    "lightgbm_production": {
      "pr_auc": 0.9994,
      "roc_auc": 1.0,
      "recall_at_1pct_fpr": 1.0,
      "onnx_export_verified": true,
      "onnx_max_abs_diff_1000_samples": 5.9314184885703605e-08,
      "onnx_parity_passed": true
    }
  },
  "cost_matrix": {
    "missed_fraud_cost": 50.0,
    "confirmation_prompt_cost": 1.0,
    "wrong_hold_cost": 5.0
  },
  "chosen_thresholds": {
    "t_low": 0.05,
    "t_med": 0.35,
    "t_high": 0.65,
    "human_review_amount": 5000.0
  },
  "external_benchmarks": {
    "dataset": "creditcard.csv",
    "source": "ULB Machine Learning Group (Real Credit Card Transactions)",
    "rows_evaluated": 100000,
    "test_fraud_count": 48,
    "pr_auc": 0.2803,
    "roc_auc": 0.8857,
    "recall_at_1pct_fpr": 0.7708,
    "note": "Real-world dataset baseline showing expected non-saturated metrics with authentic transactional noise."
  }
}
```

### Latency Performance ([`reports/latency.json`](reports/latency.json)):
- **Total Transactions Replayed:** 100,000
- **Throughput:** 4,890.1 transactions / second
- **p50 Latency:** 0.105 ms (104.6 µs)
- **p95 Latency:** 0.320 ms (319.5 µs)
- **p99 Latency:** 0.492 ms (491.7 µs)

---

## 6. How to Reproduce Metrics

1. **Generate Data:**
   ```bash
   python src/generate_data.py
   ```
2. **Train Models and Export ONNX:**
   ```bash
   python src/train.py
   ```
3. **Run 100k Replay Benchmark:**
   ```bash
   python src/replay.py
   ```
4. **Run Fairness Audit:**
   ```bash
   python src/fairness.py
   ```
5. **Run Test Suites:**
   ```bash
   python -m pytest tests/ -v
   ```

---

## 7. 3-Minute Demo Script

- **Minute 0:00 – 0:30 | The Critical Decision Context & Model Transparency**
  - Open `http://127.0.0.1:8000`. Point out the header badge: `Backend: LOCAL_ONNX` with sub-0.50ms p99 response times (measured 0.492 ms at 4,890 txn/sec).
  - Explain the IBM Z Datathon theme: Real-Time AI for Critical Decisions. In payments, the critical decision happens in the ~50ms payment authorization window before funds are irrevocably cleared.
  - **Be transparent with judges on metrics:** State clearly that the synthetic payment dataset achieves ROC-AUC 1.0 because the planted attack patterns have distinct behavioral signatures designed to prove feature extraction and ONNX execution mechanics. Then point to the **Real Data Baseline (ULB Credit Card)** in the Model Metrics panel (ROC-AUC 0.8857, Recall@1% FPR 0.7708) to demonstrate authentic real-world model performance on noisy transactions.
- **Minute 0:30 – 1:30 | Live Stream & Injected Attack Patterns**
  - Click **Start Stream** and adjust speed to **5x**. Watch normal transactions stream in with green `[ALLOW]` badges.
  - Click the **New Payee ($4.5k)** scenario button. An immediate `[HOLD]` decision flashes in the feed.
  - Click the **Mule Fan-In** scenario button. Show how the feature store detected that 18 distinct victims transferred funds to this mule today, triggering step-up confirmation `[CONFIRM]`.
  - Click the **Account Takeover** button. Show how a new device at 03:00 submitting $5,200 is escalated to `[HUMAN_REVIEW]`.
- **Minute 1:30 – 2:15 | Explainability & Human Agency**
  - Look at the **Customer Notification View** panel. Highlight the plain English sentence: *"You have never sent a payment to this recipient account before."*
  - Emphasize Rule 1 & Explainability rules: this explanation was derived strictly from LightGBM tree SHAP contributions mapped to a deterministic template—zero hallucinated LLM text.
  - In the decision feed, click **Release payment** on a held item and **Confirm payment** on a step-up card, showing interactive resolution.
- **Minute 2:15 – 3:00 | Vulnerable Customers & Algorithmic Fairness**
  - Toggle **Vulnerable Mode** switch in the header.
  - Run the manual payment form with amount `$3,400`. Notice how vulnerable customer protections escalate the decision by one full band and trigger the *"🛡️ Trusted Contact Alert"* safeguard.
  - Review the **Fairness & Disparate Impact Audit Table**: confirm that hold rates across `18-34`, `35-59`, and `60+` maintain a demographic gap $< 0.05$ (Status: `FAIR`).
  - Click **Export Audit CSV** to download `scamshield_audit_log.csv`.

---

## 8. Known Limitations

1. **Local vs Enterprise AI Accelerator:** While this demo runs locally using ONNX Runtime on CPU, production IBM Z deployments run models directly on the Telum processor's dedicated Neural Network Processing Assist (NNPA) coprocessor via IBM Watson Machine Learning for z/OS.
2. **Synthetic vs Real Data Realism:** The synthetic dataset has 60 test fraud cases planted with distinct behavioral signatures, yielding near-perfect separation (ROC-AUC 1.0) to prove pipeline mechanics. In contrast, real banking data contains subtle adversarial shifts—as illustrated by our genuine ULB benchmark (ROC-AUC 0.8857, PR-AUC 0.2803).
3. **Generative Rewrite Hook:** An optional generative text rewriter hook is provided in `src/explain.py` but is intentionally kept `OFF` by default to prevent non-deterministic language generation in critical regulatory banking compliance paths.

---

## 9. Open-Source Resources, Datasets, and Licenses

### Core Machine Learning & Model Export
- **LightGBM:** High-performance gradient boosting framework.  
  - Repository: [https://github.com/microsoft/LightGBM](https://github.com/microsoft/LightGBM) | License: MIT
- **ONNX (Open Neural Network Exchange):** Open standard format for machine learning interoperability.  
  - Website: [https://onnx.ai](https://onnx.ai) | Repository: [https://github.com/onnx/onnx](https://github.com/onnx/onnx) | License: Apache 2.0
- **ONNX Runtime:** High-performance scoring engine for ONNX models across hardware backends.  
  - Website: [https://onnxruntime.ai](https://onnxruntime.ai) | Repository: [https://github.com/microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) | License: MIT
- **skl2onnx & onnxmltools:** Converters for scikit-learn and tree-based pipelines to ONNX.  
  - skl2onnx: [https://github.com/onnx/sklearn-onnx](https://github.com/onnx/sklearn-onnx) | License: Apache 2.0  
  - onnxmltools: [https://github.com/onnx/onnxmltools](https://github.com/onnx/onnxmltools) | License: Apache 2.0
- **scikit-learn:** Baseline machine learning algorithms and evaluation metrics.  
  - Website: [https://scikit-learn.org](https://scikit-learn.org) | Repository: [https://github.com/scikit-learn/scikit-learn](https://github.com/scikit-learn/scikit-learn) | License: BSD 3-Clause
- **NumPy & Pandas:** High-performance array computation and data structures.  
  - NumPy: [https://numpy.org](https://numpy.org) | Repository: [https://github.com/numpy/numpy](https://github.com/numpy/numpy) | License: BSD 3-Clause  
  - Pandas: [https://pandas.pydata.org](https://pandas.pydata.org) | Repository: [https://github.com/pandas-dev/pandas](https://github.com/pandas-dev/pandas) | License: BSD 3-Clause

### Backend, API & Streaming
- **FastAPI:** High-performance modern web framework for building APIs with Python 3.8+.  
  - Website: [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com) | Repository: [https://github.com/fastapi/fastapi](https://github.com/fastapi/fastapi) | License: MIT
- **Uvicorn:** Lightning-fast ASGI web server implementation.  
  - Website: [https://www.uvicorn.org](https://www.uvicorn.org) | Repository: [https://github.com/encode/uvicorn](https://github.com/encode/uvicorn) | License: BSD 3-Clause
- **Pydantic:** Data validation and settings management using Python type annotations.  
  - Website: [https://docs.pydantic.dev](https://docs.pydantic.dev) | Repository: [https://github.com/pydantic/pydantic](https://github.com/pydantic/pydantic) | License: MIT
- **PyYAML:** YAML parser and emitter for Python configuration loading.  
  - Website: [https://pyyaml.org](https://pyyaml.org) | Repository: [https://github.com/yaml/pyyaml](https://github.com/yaml/pyyaml) | License: MIT

### Frontend & Data Visualization
- **Chart.js:** Simple yet flexible JavaScript charting for designers & developers (bundled locally for offline execution in `static/chart.umd.min.js`).  
  - Website: [https://www.chartjs.org](https://www.chartjs.org) | Repository: [https://github.com/chartjs/Chart.js](https://github.com/chartjs/Chart.js) | License: MIT

### Testing, Parity & End-to-End Verification
- **Pytest:** Comprehensive Python testing framework.  
  - Website: [https://pytest.org](https://pytest.org) | Repository: [https://github.com/pytest-dev/pytest](https://github.com/pytest-dev/pytest) | License: MIT
- **Playwright for Python:** Cross-browser headless UI automation and console verification.  
  - Website: [https://playwright.dev/python](https://playwright.dev/python) | Repository: [https://github.com/microsoft/playwright-python](https://github.com/microsoft/playwright-python) | License: Apache 2.0

### Datasets & Benchmarks
- **ULB Machine Learning Group Credit Card Fraud Detection:** Real-world European credit card transaction dataset with authentic fraud noise.  
  - Kaggle: [https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)  
  - Academic Origin: Machine Learning Group - Université Libre de Bruxelles ([http://mlg.ulb.ac.be](http://mlg.ulb.ac.be))  
  - License: Open Database License (ODbL) 1.0
- **PaySim Synthetic Financial Simulator:** Agent-based synthetic financial simulator based on mobile money transactions.  
  - Kaggle: [https://www.kaggle.com/datasets/ealaxi/paysim1](https://www.kaggle.com/datasets/ealaxi/paysim1)  
  - Paper: Lopez-Rojas et al., "PaySim: A financial mobile money simulator for fraud detection" ([ResearchGate](https://www.researchgate.net/publication/313138087_PaySim_A_financial_mobile_money_simulator_for_fraud_detection))  
  - License: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
- **ScamShield Primary Stream:** Seeded, synthetically generated payment stream created by `src/generate_data.py`. All events and IDs are generated locally and marked with `[SYNTHETIC DATA]`.  
  - License: Apache 2.0

