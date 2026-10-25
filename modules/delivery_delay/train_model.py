"""Main Model Training and Comparison Pipeline for Delivery Delay Prediction.

Trains:
- RandomForestClassifier (Main Model, version 1.0 "delivery-delay-model")
Compares against:
- Majority-Class Baseline
- Logistic Regression Baseline

Evaluates:
- Precision, Recall, F1, Confusion Matrix, ROC-AUC
Extracts:
- Top 5 Feature Importances
Saves:
- Model + Feature Pipeline together into artifacts/
"""

from typing import Any, Dict
import numpy as np
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
from modules.delivery_delay.model import DeliveryDelayModel
from modules.delivery_delay.preprocessing import create_target_and_features


def evaluate_estimator(clf: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
    """Calculate standard evaluation metrics on test set."""
    y_pred = clf.predict(X_test)
    if hasattr(clf, "predict_proba"):
        y_prob = clf.predict_proba(X_test)[:, 1]
    else:
        y_prob = y_pred

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    try:
        auc = float(roc_auc_score(y_test, y_prob))
    except ValueError:
        auc = 0.5

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "roc_auc": auc,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def run_full_training_and_comparison():
    """Execute end-to-end training, comparative evaluation, and model serialization."""
    print("=" * 75)
    print("INTELLIOPS — DELIVERY DELAY PREDICTION: MODEL TRAINING & BENCHMARK")
    print("=" * 75)

    # 1. Load data
    df, _ = load_raw_dataset(verbose=False)
    X, y = create_target_and_features(df)

    # 2. Stratified 75/25 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    print(f"Total samples: {len(df)} | Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"Target distribution (Delayed=1 / On-Time=0): {y.sum()} / {len(y) - y.sum()}")

    # 3. Fit feature pipeline on train ONLY
    pipeline = DeliveryDelayFeaturePipeline()
    X_train_trans = pipeline.fit_transform(X_train)
    X_test_trans = pipeline.transform(X_test)

    # 4. Baseline 1: Majority Class
    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit(X_train_trans, y_train.values)
    dummy_metrics = evaluate_estimator(dummy, X_test_trans, y_test.values)

    # 5. Baseline 2: Logistic Regression
    lr = LogisticRegression(random_state=42, max_iter=1000)
    lr.fit(X_train_trans, y_train.values)
    lr_metrics = evaluate_estimator(lr, X_test_trans, y_test.values)

    # 6. Main Model: RandomForest
    model = DeliveryDelayModel(model_name="delivery-delay-model", version="1.0")
    model.train(
        X_train_trans,
        y_train.values,
        feature_pipeline=pipeline,
        n_estimators=100,
        max_depth=5,
        random_state=42,
    )
    rf_metrics = evaluate_estimator(model, X_test_trans, y_test.values)

    # 7. Save model + preprocessor together
    saved_path = model.save()
    print(f"\nModel and preprocessor saved successfully to: {saved_path}")

    # 8. Feature Importances
    top_5 = model.get_top_features(top_k=5)

    # 9. Format comparative table
    print("\n" + "=" * 75)
    print("COMPARATIVE BENCHMARK: BASELINES VS. RANDOM FOREST (MAIN MODEL)")
    print("=" * 75)
    header = f"{'Metric':<25} | {'Majority Class':<15} | {'Logistic Reg':<15} | {'Random Forest (v1.0)':<20}"
    print(header)
    print("-" * 75)

    rows = [
        ("Accuracy", dummy_metrics["accuracy"], lr_metrics["accuracy"], rf_metrics["accuracy"]),
        ("Precision (Delayed)", dummy_metrics["precision"], lr_metrics["precision"], rf_metrics["precision"]),
        ("Recall (Delayed)", dummy_metrics["recall"], lr_metrics["recall"], rf_metrics["recall"]),
        ("F1-Score", dummy_metrics["f1_score"], lr_metrics["f1_score"], rf_metrics["f1_score"]),
        ("ROC-AUC", dummy_metrics["roc_auc"], lr_metrics["roc_auc"], rf_metrics["roc_auc"]),
    ]

    for name, d_val, lr_val, rf_val in rows:
        print(f"{name:<25} | {d_val:<15.4f} | {lr_val:<15.4f} | {rf_val:<20.4f}")

    print("-" * 75)
    print("CONFUSION MATRICES (TN, FP, FN, TP):")
    print(f"  Majority Class: {dummy_metrics['confusion_matrix']}")
    print(f"  Logistic Reg:   {lr_metrics['confusion_matrix']}")
    print(f"  Random Forest:  {rf_metrics['confusion_matrix']}")

    print("\n" + "=" * 75)
    print("TOP 5 IMPORTANT FEATURES (Random Forest):")
    print("=" * 75)
    for rank, (feat, imp) in enumerate(top_5, 1):
        print(f"  {rank}. {feat:<30} Importance: {imp:.4f} ({imp*100:.1f}%)")
    print("=" * 75)

    return dummy_metrics, lr_metrics, rf_metrics, top_5


if __name__ == "__main__":
    run_full_training_and_comparison()
