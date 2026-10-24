import os
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from modules.sales_revenue_forecasting.preprocessing import create_lagged_features

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "sample_monthly_sales.csv"
MODEL_ARTIFACT_PATH = MODULE_DIR / "sales_model.joblib"


def train_sales_forecasting_model(
    data_path: Path = DEFAULT_DATA_PATH,
    artifact_path: Path = MODEL_ARTIFACT_PATH,
    test_horizon_months: int = 6,
) -> dict:
    """Train a time-series regression model on chronological data.

    Evaluation strictly enforces chronological ordering (no future data leakage).
    """
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset not found at {data_path}")

    # Read CSV, ignoring comment lines starting with #
    df = pd.read_csv(data_path, comment="#")

    required_cols = {"historical_sales", "marketing_budget", "seasonality_factor", "discount_rate_pct"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    # Create chronological lagged features
    featured_df = create_lagged_features(df, target_col="historical_sales", max_lag=2, rolling_window=3)

    feature_cols = [
        "lag_1",
        "lag_2",
        "rolling_mean_3",
        "marketing_budget",
        "seasonality_factor",
        "discount_rate_pct",
    ]

    total_samples = len(featured_df)
    if total_samples <= test_horizon_months:
        raise ValueError(
            f"Insufficient samples ({total_samples}) for a {test_horizon_months}-month holdout test split."
        )

    # Strictly chronological train/test split: older data for train, newer for test
    train_df = featured_df.iloc[:-test_horizon_months]
    test_df = featured_df.iloc[-test_horizon_months:]

    X_train = train_df[feature_cols]
    y_train = train_df["historical_sales"]

    X_test = test_df[feature_cols]
    y_test = test_df["historical_sales"]

    # Build regularized linear pipeline
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("regressor", Ridge(alpha=1.0)),
    ])

    pipeline.fit(X_train, y_train)

    # Evaluate on chronological hold-out test set
    y_pred = pipeline.predict(X_test)
    test_mae = float(mean_absolute_error(y_test, y_pred))
    test_rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    test_r2 = float(r2_score(y_test, y_pred))

    artifact = {
        "pipeline": pipeline,
        "feature_cols": feature_cols,
        "metrics": {
            "test_mae": round(test_mae, 2),
            "test_rmse": round(test_rmse, 2),
            "test_r2": round(test_r2, 4),
            "train_samples": len(train_df),
            "test_samples": len(test_df),
        },
        "metadata": {
            "model_type": "Ridge Regression with Scaler",
            "validation_split": "Chronological hold-out (last 6 months)",
            "purpose": "Benchmark ML model trained on multi-feature monthly sales history",
        },
    }

    joblib.dump(artifact, artifact_path)

    return artifact


if __name__ == "__main__":
    result = train_sales_forecasting_model()
    print("Model successfully trained and saved!")
    print("Metrics:", result["metrics"])
