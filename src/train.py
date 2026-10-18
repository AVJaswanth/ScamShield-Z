"""
ScamShield Z: Model Training, ONNX Export & Parity Verification
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

- Time-based 70/15/15 chronological split (no shuffle, zero future leakage)
- Logistic Regression baseline with balanced weighting
- LightGBM with scale_pos_weight
- Conversion to ONNX format (models/lgbm_scam.onnx)
- Strict Parity Check: assert |LightGBM - ONNX| < 1e-5 on 1,000 samples
- Cost-tuned policy thresholds ($50 missed fraud, $1 prompt, $5 false hold)
- Generation of reports/metrics.json
- Optional evaluation on data/external/creditcard.csv / PaySim
"""

import os
import sys

# Ensure repository root and src directory are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import json
import yaml
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
import lightgbm as lgb
import onnxruntime as ort
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType

from src.features import FeatureStore, compute_features, to_feature_vector, FEATURE_NAMES


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.join(BASE_DIR, "config.yaml")
    elif not os.path.isabs(config_path) and not os.path.exists(config_path):
        config_path = os.path.join(BASE_DIR, config_path)

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "training": {"train_split": 0.70, "val_split": 0.15, "test_split": 0.15, "parity_tolerance": 1e-5},
        "costs": {"missed_fraud": 50.0, "confirmation_prompt": 1.0, "wrong_hold": 5.0}
    }


def compute_recall_at_fpr(y_true, y_prob, target_fpr=0.01):
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    idx = np.where(fpr <= target_fpr)[0]
    if len(idx) > 0:
        best_idx = idx[-1]
        return float(tpr[best_idx])
    return 0.0


def tune_cost_thresholds(y_val, probs_val, costs):
    """
    Tune policy thresholds (t_low, t_med, t_high) on validation set to minimize business cost:
    - Missed fraud (FN): $50
    - Confirmation prompt friction (Medium band): $1
    - False Hold friction (High/Very High band): $5
    """
    c_miss = costs.get("missed_fraud", 50.0)
    c_prompt = costs.get("confirmation_prompt", 1.0)
    c_hold = costs.get("wrong_hold", 5.0)

    # Grid search across reasonable operational intervals
    best_cost = float("inf")
    best_t_low = 0.15
    best_t_med = 0.45
    best_t_high = 0.75

    t_candidates = np.linspace(0.05, 0.90, 18)
    for t_l in t_candidates[:7]:         # 0.05 to 0.35
        for t_m in t_candidates[6:13]:   # 0.35 to 0.65
            if t_m <= t_l:
                continue
            for t_h in t_candidates[12:]: # 0.65 to 0.90
                if t_h <= t_m:
                    continue

                # Band decisions:
                # < t_l -> Allow (FN if fraud)
                # t_l <= p < t_m -> Notice/Confirm (Prompt cost if legit, stopped if fraud)
                # t_m <= p < t_h -> Confirm
                # >= t_h -> Hold (Hold cost if legit, stopped if fraud)

                is_fraud = (y_val == 1)
                is_legit = (y_val == 0)

                # Missed fraud: fraud scored < t_l
                missed = np.sum(is_fraud & (probs_val < t_l))
                # Prompts on legit users:
                prompts = np.sum(is_legit & (probs_val >= t_l) & (probs_val < t_h))
                # Holds on legit users:
                holds = np.sum(is_legit & (probs_val >= t_h))

                total_cost = (missed * c_miss) + (prompts * c_prompt) + (holds * c_hold)
                if total_cost < best_cost:
                    best_cost = total_cost
                    best_t_low = float(t_l)
                    best_t_med = float(t_m)
                    best_t_high = float(t_h)

    return round(best_t_low, 3), round(best_t_med, 3), round(best_t_high, 3), round(best_cost, 2)


def train_models(data_path="data/synthetic_payments.csv", config_path="config.yaml"):
    if not os.path.isabs(data_path) and not os.path.exists(data_path):
        data_path = os.path.join(BASE_DIR, data_path)
    cfg = load_config(config_path)
    train_split = cfg.get("training", {}).get("train_split", 0.70)
    val_split = cfg.get("training", {}).get("val_split", 0.15)
    parity_tol = cfg.get("training", {}).get("parity_tolerance", 1e-5)
    costs = cfg.get("costs", {"missed_fraud": 50.0, "confirmation_prompt": 1.0, "wrong_hold": 5.0})

    print(f"Loading dataset from {data_path}...")
    df = pd.read_csv(data_path)
    print(f"Total events loaded: {len(df):,}")

    # Process features in strict chronological order with fresh FeatureStore
    print("Extracting 16 behavioral features using rolling FeatureStore (zero future leakage)...")
    store = FeatureStore()
    feature_matrix = []
    labels = df["is_fraud"].values

    for idx, row in df.iterrows():
        ev = row.to_dict()
        feat_dict = compute_features(ev, store, update_store=True)
        feature_matrix.append(to_feature_vector(feat_dict))

    X = np.array(feature_matrix, dtype=np.float32)
    y = np.array(labels, dtype=np.int32)

    total_rows = len(X)
    idx_train = int(total_rows * train_split)
    idx_val = int(total_rows * (train_split + val_split))

    X_train, y_train = X[:idx_train], y[:idx_train]
    X_val, y_val = X[idx_train:idx_val], y[idx_train:idx_val]
    X_test, y_test = X[idx_val:], y[idx_val:]

    print(f"Chronological split -> Train: {len(X_train):,}, Val: {len(X_val):,}, Test: {len(X_test):,}")
    print(f"Test Fraud Count: {np.sum(y_test):,} / {len(y_test):,} ({np.mean(y_test)*100:.3f}%)")

    # 1. Baseline Model: Logistic Regression
    print("\n--- Training Baseline Logistic Regression ---")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    lr = LogisticRegression(class_weight="balanced", max_iter=500, random_state=42)
    lr.fit(X_train_scaled, y_train)
    lr_probs = lr.predict_proba(X_test_scaled)[:, 1]

    lr_pr_auc = float(average_precision_score(y_test, lr_probs))
    lr_roc_auc = float(roc_auc_score(y_test, lr_probs))
    lr_recall_1pct = float(compute_recall_at_fpr(y_test, lr_probs, target_fpr=0.01))
    print(f"Baseline LR  -> PR-AUC: {lr_pr_auc:.4f} | ROC-AUC: {lr_roc_auc:.4f} | Recall@1% FPR: {lr_recall_1pct:.4f}")

    # 2. Production Model: LightGBM
    print("\n--- Training Production LightGBM Classifier ---")
    # Imbalanced ratio ~ 200:1, use scale_pos_weight ~ 20
    lgbm = lgb.LGBMClassifier(
        n_estimators=120,
        learning_rate=0.07,
        num_leaves=31,
        scale_pos_weight=20.0,
        random_state=42,
        verbosity=-1
    )
    lgbm.fit(X_train, y_train, eval_set=[(X_val, y_val)])

    lgbm_probs = lgbm.predict_proba(X_test)[:, 1]
    lgbm_pr_auc = float(average_precision_score(y_test, lgbm_probs))
    lgbm_roc_auc = float(roc_auc_score(y_test, lgbm_probs))
    lgbm_recall_1pct = float(compute_recall_at_fpr(y_test, lgbm_probs, target_fpr=0.01))
    print(f"LightGBM     -> PR-AUC: {lgbm_pr_auc:.4f} | ROC-AUC: {lgbm_roc_auc:.4f} | Recall@1% FPR: {lgbm_recall_1pct:.4f}")

    # Save Booster model for Tree SHAP / pred_contrib
    models_dir = os.path.join(BASE_DIR, "models")
    os.makedirs(models_dir, exist_ok=True)
    booster_path = os.path.join(models_dir, "lgbm_booster.txt")
    lgbm.booster_.save_model(booster_path)
    print(f"Saved LightGBM booster model to {booster_path}")

    # 3. Export to ONNX
    print("\n--- Converting LightGBM to ONNX ---")
    initial_type = [("float_input", FloatTensorType([None, 16]))]
    onnx_model = onnxmltools.convert_lightgbm(
        lgbm,
        initial_types=initial_type,
        target_opset=15
    )

    onnx_path = os.path.join(models_dir, "lgbm_scam.onnx")
    onnxmltools.utils.save_model(onnx_model, onnx_path)
    print(f"Exported ONNX model to {onnx_path}")

    # 4. Parity Check on 1,000 samples
    print("\n--- Verifying ONNX vs LightGBM Parity on 1,000 Samples ---")
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    sample_X = X_test[:1000]
    lgbm_sample_probs = lgbm.predict_proba(sample_X)[:, 1]

    onnx_raw = session.run(None, {input_name: sample_X})
    # ONNX LightGBM classifier output[1] contains list of probability dicts or 2D array
    if len(onnx_raw) > 1:
        probs_output = onnx_raw[1]
        if isinstance(probs_output, list) and isinstance(probs_output[0], dict):
            onnx_sample_probs = np.array([p[1] for p in probs_output], dtype=np.float32)
        elif isinstance(probs_output, np.ndarray):
            onnx_sample_probs = probs_output[:, 1]
        else:
            onnx_sample_probs = np.array(probs_output, dtype=np.float32)
    else:
        onnx_sample_probs = onnx_raw[0][:, 1]

    max_diff = float(np.max(np.abs(onnx_sample_probs - lgbm_sample_probs)))
    print(f"Max absolute probability difference: {max_diff:.8e}")
    if max_diff >= parity_tol:
        raise ValueError(f"ONNX parity check failed! Max diff {max_diff} exceeds tolerance {parity_tol}")
    print(f"Parity check PASSED (|diff| < {parity_tol})")

    # 5. Tune Policy Thresholds on Validation Set
    print("\n--- Tuning Cost-Optimal Thresholds on Validation Set ---")
    val_probs = lgbm.predict_proba(X_val)[:, 1]
    t_low, t_med, t_high, opt_cost = tune_cost_thresholds(y_val, val_probs, costs)
    print(f"Tuned Thresholds -> T_low: {t_low}, T_med: {t_med}, T_high: {t_high} (Validation Cost: ${opt_cost:,.2f})")

    # 6. Check Optional External Datasets (ULB Credit Card / PaySim)
    external_benchmarks = "not measured (data/external/creditcard.csv or paysim not present)"
    external_paths = [
        os.path.join(BASE_DIR, "data", "external", "creditcard.csv"),
        os.path.join(BASE_DIR, "data", "external", "paysim.csv"),
        os.path.join(BASE_DIR, "data", "creditcard.csv"),
        "data/external/creditcard.csv"
    ]
    for ext_p in external_paths:
        if os.path.exists(ext_p):
            print(f"Found optional external benchmark dataset at {ext_p}, evaluating...")
            try:
                # Load up to 100,000 rows for real-world benchmarking
                ext_df = pd.read_csv(ext_p, nrows=100000)
                target_col = "Class" if "Class" in ext_df.columns else ("isFraud" if "isFraud" in ext_df.columns else None)
                if target_col and target_col in ext_df.columns:
                    ext_y = ext_df[target_col].astype(int).values
                    ext_X = ext_df.drop(columns=[target_col]).select_dtypes(include=[np.number]).fillna(0).values
                    ext_split = int(len(ext_X) * 0.70)
                    X_tr, y_tr = ext_X[:ext_split], ext_y[:ext_split]
                    X_te, y_te = ext_X[ext_split:], ext_y[ext_split:]

                    ext_lgbm = lgb.LGBMClassifier(
                        n_estimators=80,
                        learning_rate=0.08,
                        scale_pos_weight=10.0,
                        random_state=42,
                        verbosity=-1
                    )
                    ext_lgbm.fit(X_tr, y_tr)
                    ext_probs = ext_lgbm.predict_proba(X_te)[:, 1]

                    ext_pr_auc = float(average_precision_score(y_te, ext_probs))
                    ext_roc_auc = float(roc_auc_score(y_te, ext_probs))
                    ext_recall_1pct = float(compute_recall_at_fpr(y_te, ext_probs, target_fpr=0.01))

                    external_benchmarks = {
                        "dataset": os.path.basename(ext_p),
                        "source": "ULB Machine Learning Group (Real Credit Card Transactions)" if "creditcard" in ext_p.lower() else "PaySim Financial Simulator",
                        "rows_evaluated": len(ext_df),
                        "test_fraud_count": int(np.sum(y_te)),
                        "pr_auc": round(ext_pr_auc, 4),
                        "roc_auc": round(ext_roc_auc, 4),
                        "recall_at_1pct_fpr": round(ext_recall_1pct, 4),
                        "note": "Real-world dataset baseline showing expected non-saturated metrics with authentic transactional noise."
                    }
                    print(f"External Benchmark ({os.path.basename(ext_p)}) -> PR-AUC: {ext_pr_auc:.4f} | ROC-AUC: {ext_roc_auc:.4f} | Recall@1% FPR: {ext_recall_1pct:.4f}")
            except Exception as e:
                print(f"External benchmark warning: {e}")
                external_benchmarks = f"error benchmarking external data: {str(e)}"
            break

    # 7. Write reports/metrics.json
    os.makedirs("reports", exist_ok=True)
    metrics_report = {
        "synthetic_data": True,
        "data_label": "[SYNTHETIC DATA]",
        "synthetic_data_disclaimer": "Metrics on synthetic_payments.csv reflect clean separation of the planted fraud patterns (demonstrating feature extraction & ONNX pipeline integrity). They do not represent real-world deployment accuracy on noisy bank data. See external_benchmarks (ULB Credit Card) for real-world baseline.",
        "total_events": total_rows,
        "splits": {
            "train_events": len(X_train),
            "val_events": len(X_val),
            "test_events": len(X_test),
            "test_fraud_count": int(np.sum(y_test))
        },
        "models": {
            "baseline_logistic_regression": {
                "pr_auc": round(lr_pr_auc, 4),
                "roc_auc": round(lr_roc_auc, 4),
                "recall_at_1pct_fpr": round(lr_recall_1pct, 4)
            },
            "lightgbm_production": {
                "pr_auc": round(lgbm_pr_auc, 4),
                "roc_auc": round(lgbm_roc_auc, 4),
                "recall_at_1pct_fpr": round(lgbm_recall_1pct, 4),
                "onnx_export_verified": True,
                "onnx_max_abs_diff_1000_samples": float(max_diff),
                "onnx_parity_passed": bool(max_diff < parity_tol)
            }
        },
        "cost_matrix": {
            "missed_fraud_cost": costs.get("missed_fraud", 50.0),
            "confirmation_prompt_cost": costs.get("confirmation_prompt", 1.0),
            "wrong_hold_cost": costs.get("wrong_hold", 5.0)
        },
        "chosen_thresholds": {
            "t_low": t_low,
            "t_med": t_med,
            "t_high": t_high,
            "human_review_amount": cfg.get("policy", {}).get("human_review_amount", 5000.0)
        },
        "external_benchmarks": external_benchmarks
    }

    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    metrics_path = os.path.join(reports_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_report, f, indent=2)
    print(f"\nWrote full metrics report to {metrics_path}")


if __name__ == "__main__":
    train_models()
