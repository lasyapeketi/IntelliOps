import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier

from app.config import DATASET_PATH, MODEL_DIR, MODEL_PATH, METRICS_PATH

TARGET = "Attrition"
EXCLUDED = {
    TARGET, "EmployeeNumber", "EmployeeCount", "Over18", "StandardHours",
    # Excluded from this educational model to reduce use of demographic proxies.
    "Age", "Gender", "MaritalStatus",
}

def main():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}\n"
            "Download the IBM HR Analytics CSV from Kaggle and place it in backend/data/."
        )

    df = pd.read_csv(DATASET_PATH)
    if TARGET not in df.columns:
        raise ValueError(f"Expected target column '{TARGET}' in the CSV.")

    df = df.dropna(subset=[TARGET]).copy()
    y = df[TARGET].astype(str).str.strip().str.lower().map({"yes": 1, "no": 0})
    if y.isna().any():
        raise ValueError("Attrition column must contain Yes/No labels.")

    feature_cols = [c for c in df.columns if c not in EXCLUDED]
    X = df[feature_cols].copy()
    if not feature_cols:
        raise ValueError("No usable feature columns found.")

    categorical = X.select_dtypes(include=["object", "category"]).columns.tolist()
    numeric = [c for c in X.columns if c not in categorical]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), numeric),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]), categorical),
        ],
        remainder="drop",
    )

    pipeline = Pipeline([
        ("preprocess", preprocessor),
        ("model", RandomForestClassifier(
            n_estimators=350,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    pipeline.fit(X_train, y_train)
    probabilities = pipeline.predict_proba(X_test)[:, 1]
    # Use the demonstration threshold for reporting; tune it for your use case.
    threshold = 0.40
    predictions = (probabilities >= threshold).astype(int)

    try:
        auc = float(roc_auc_score(y_test, probabilities))
    except ValueError:
        auc = None

    metrics = {
        "dataset_rows": int(len(df)),
        "feature_count": int(len(feature_cols)),
        "positive_count": int(y.sum()),
        "historical_attrition_rate": round(float(y.mean()) * 100, 2),
        "test_rows": int(len(y_test)),
        "threshold": threshold,
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
        "roc_auc": round(auc, 4) if auc is not None else None,
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=[0, 1]).tolist(),
        "feature_columns": feature_cols,
        "categorical_columns": categorical,
        "numeric_columns": numeric,
        "excluded_columns": sorted(EXCLUDED),
        "model_name": "Random Forest classifier",
        "note": "Metrics are from a held-out split of fictional public data; not evidence of real-world performance.",
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "feature_columns": feature_cols}, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Model saved to: {MODEL_PATH}")
    print(json.dumps({k: v for k, v in metrics.items() if k not in {"feature_columns", "categorical_columns", "numeric_columns", "excluded_columns"}}, indent=2))

if __name__ == "__main__":
    main()
