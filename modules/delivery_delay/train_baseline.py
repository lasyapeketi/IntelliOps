"""Baseline Model Training and Evaluation Script for Delivery Delay.

Trains:
1. Majority-class DummyClassifier baseline
2. Logistic Regression baseline

Evaluates using:
- Precision
- Recall
- F1-Score
- Confusion Matrix
- ROC-AUC
"""

from typing import Any, Dict, Tuple
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from modules.delivery_delay.data_loader import load_raw_dataset
from modules.delivery_delay.features import DeliveryDelayFeaturePipeline
from modules.delivery_delay.preprocessing import create_target_and_features


def evaluate_classifier(
    clf: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_name: str,
) -> Dict[str, Any]:
    """Train estimator and compute comprehensive binary classification metrics."""
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)

    # Probabilities for ROC-AUC
    if hasattr(clf, "predict_proba"):
        y_prob = clf.predict_proba(X_test)[:, 1]
    else:
        y_prob = y_pred

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    try:
        auc = roc_auc_score(y_test, y_prob)
    except ValueError:
        auc = 0.5

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    return {
        "model_name": model_name,
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "roc_auc": auc,
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def run_baseline_evaluation() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute stratified split and baseline benchmarking."""
    print("Loading cleaned dataset...")
    df, summary = load_raw_dataset(verbose=False)
    X, y = create_target_and_features(df)

    # Stratified 75/25 split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    print(f"Dataset summary: Total={len(df)} | Delayed=int({y.sum()}) | On-time=int({len(y)-y.sum()})")
    print(f"Train samples: {len(X_train)} | Test samples: {len(X_test)}")

    # Feature transformation (fit strictly on train)
    pipeline = DeliveryDelayFeaturePipeline()
    X_train_trans = pipeline.fit_transform(X_train)
    X_test_trans = pipeline.transform(X_test)

    # 1. Baseline 1: Majority-class
    dummy = DummyClassifier(strategy="most_frequent")
    metrics_dummy = evaluate_classifier(
        dummy, X_train_trans, y_train.values, X_test_trans, y_test.values, "Majority-Class Baseline"
    )

    # 2. Baseline 2: Logistic Regression
    lr = LogisticRegression(random_state=42, C=1.0, max_iter=1000)
    metrics_lr = evaluate_classifier(
        lr, X_train_trans, y_train.values, X_test_trans, y_test.values, "Logistic Regression Baseline"
    )

    return metrics_dummy, metrics_lr


def print_metrics_table(metrics_dummy: Dict[str, Any], metrics_lr: Dict[str, Any]) -> str:
    """Format evaluation results into a clear markdown table."""
    table_str = """
| Metric | Majority-Class Baseline | Logistic Regression Baseline |
|---|---|---|
| Accuracy | {:.4f} | {:.4f} |
| Precision (Delayed) | {:.4f} | {:.4f} |
| Recall (Delayed) | {:.4f} | {:.4f} |
| F1-Score | {:.4f} | {:.4f} |
| ROC-AUC | {:.4f} | {:.4f} |
| Confusion Matrix (TN, FP, FN, TP) | TN={}, FP={}, FN={}, TP={} | TN={}, FP={}, FN={}, TP={} |
""".strip().format(
        metrics_dummy["accuracy"],
        metrics_lr["accuracy"],
        metrics_dummy["precision"],
        metrics_lr["precision"],
        metrics_dummy["recall"],
        metrics_lr["recall"],
        metrics_dummy["f1_score"],
        metrics_lr["f1_score"],
        metrics_dummy["roc_auc"],
        metrics_lr["roc_auc"],
        metrics_dummy["confusion_matrix"]["tn"],
        metrics_dummy["confusion_matrix"]["fp"],
        metrics_dummy["confusion_matrix"]["fn"],
        metrics_dummy["confusion_matrix"]["tp"],
        metrics_lr["confusion_matrix"]["tn"],
        metrics_lr["confusion_matrix"]["fp"],
        metrics_lr["confusion_matrix"]["fn"],
        metrics_lr["confusion_matrix"]["tp"],
    )
    return table_str


if __name__ == "__main__":
    dummy_results, lr_results = run_baseline_evaluation()
    table = print_metrics_table(dummy_results, lr_results)
    print("\n" + "=" * 70)
    print("BASELINE EVALUATION BENCHMARK (Stratified 75/25 Split)")
    print("=" * 70)
    print(table)
    print("=" * 70)
