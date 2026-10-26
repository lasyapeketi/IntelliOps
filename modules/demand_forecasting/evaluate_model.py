"""Evaluate the saved demand model on its chronological holdout and report results."""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.demand_forecasting.train_model import (
    BASE_FEATURE_COLUMNS,
    DATA_PATH,
    DATE_COLUMN,
    METRICS_PATH,
    MODEL_PATH,
    PRODUCT_COLUMN,
    TARGET_COLUMN,
    add_features,
    load_dataset,
    make_baseline_model,
    nonnegative_predictions,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_DIR / "reports"
PREDICTIONS_PATH = REPORTS_DIR / "test_predictions.csv"
REPORT_PATH = REPORTS_DIR / "evaluation_report.json"
PLOT_PATH = REPORTS_DIR / "actual_vs_predicted_demand.png"


def calculate_metrics(actual, predicted):
    """Calculate MAE, RMSE, and nonzero-target MAPE when it is defined."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    errors = actual - predicted

    nonzero_actual = actual != 0
    mape = None
    if nonzero_actual.any():
        mape = float(
            np.mean(
                np.abs(errors[nonzero_actual] / actual[nonzero_actual])
            )
            * 100
        )

    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mape_percent": mape,
        "mape_observations": int(nonzero_actual.sum()),
        "mape_excluded_zero_actuals": int((~nonzero_actual).sum()),
    }


def load_json(path):
    """Read a required JSON file and report malformed content clearly."""
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path.name}: {error}") from error


def build_holdout(frame, split_date):
    """Rebuild the original chronological split without changing the saved model."""
    featured = add_features(frame)
    featured = featured.dropna(subset=["lag_1_observation"]).copy()
    split_date = pd.Timestamp(split_date)
    training = featured.loc[featured[DATE_COLUMN] < split_date].copy()
    testing = featured.loc[featured[DATE_COLUMN] >= split_date].copy()
    if training.empty or testing.empty:
        raise ValueError("The recorded chronological split has an empty partition.")
    return training, testing


def validate_artifacts(bundle, saved_metrics):
    """Ensure saved model metadata and recorded evaluation identify this split."""
    if not isinstance(bundle, dict) or "model" not in bundle:
        raise ValueError("Saved model file does not contain a model bundle.")
    metadata = bundle.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Saved model bundle is missing metadata.")

    expected = {
        "dataset": DATA_PATH.name,
        "date_column": DATE_COLUMN,
        "product_column": PRODUCT_COLUMN,
        "target_column": TARGET_COLUMN,
    }
    for field, value in expected.items():
        if metadata.get(field) != value or saved_metrics.get(field) != value:
            raise ValueError(
                f"Model and metrics must both identify {field} as {value!r}."
            )
    if saved_metrics.get("split_method") != (
        "chronological, by date; no random shuffling"
    ):
        raise ValueError("Saved metrics do not describe the expected chronological split.")
    if saved_metrics.get("evaluation", "").find("Rolling one-week-ahead") != 0:
        raise ValueError("Saved metrics do not describe the expected one-week evaluation.")
    if not saved_metrics.get("split_date"):
        raise ValueError("Saved metrics are missing the chronological split date.")

    feature_columns = metadata.get("feature_columns")
    allowed_features = {
        tuple(BASE_FEATURE_COLUMNS),
        ("lag_1_observation",),
    }
    if not isinstance(feature_columns, list) or tuple(feature_columns) not in allowed_features:
        raise ValueError("Saved model has unexpected feature columns.")
    if not callable(getattr(bundle["model"], "predict", None)):
        raise ValueError("Saved model does not provide a predict method.")
    return metadata


def write_predictions(testing, training, model_bundle):
    """Generate test predictions from the saved model and a train-only baseline."""
    metadata = model_bundle["metadata"]
    feature_columns = metadata["feature_columns"]
    if not set(feature_columns).issubset(testing.columns):
        raise ValueError("Test data does not contain all saved model features.")

    predictions = nonnegative_predictions(
        model_bundle["model"],
        testing[feature_columns],
    )

    # Fit the linear autoregressive baseline only on rows before the split.
    # The lag columns for test rows use only demand observed at earlier dates.
    baseline = make_baseline_model()
    baseline.fit(
        training[["lag_1_observation"]],
        training[TARGET_COLUMN].to_numpy(dtype=float),
    )
    baseline_predictions = nonnegative_predictions(
        baseline,
        testing[["lag_1_observation"]],
    )

    output = testing[
        [DATE_COLUMN, PRODUCT_COLUMN, TARGET_COLUMN]
    ].rename(columns={TARGET_COLUMN: "actual_demand"})
    output["ml_predicted_demand"] = predictions
    output["baseline_predicted_demand"] = baseline_predictions
    output = output.rename(
        columns={
            DATE_COLUMN: "forecast_date",
            PRODUCT_COLUMN: "sku",
        }
    )
    return output.sort_values(["forecast_date", "sku"]).reset_index(drop=True)


def create_plot(predictions):
    """Plot summed actual and predicted demand by holdout week."""
    weekly = (
        predictions.groupby("forecast_date", as_index=False)[
            [
                "actual_demand",
                "ml_predicted_demand",
                "baseline_predicted_demand",
            ]
        ]
        .sum()
        .sort_values("forecast_date")
    )

    figure, axis = plt.subplots(figsize=(12, 6))
    axis.plot(
        weekly["forecast_date"],
        weekly["actual_demand"],
        label="Actual total demand",
        linewidth=2,
    )
    axis.plot(
        weekly["forecast_date"],
        weekly["ml_predicted_demand"],
        label="Machine learning model total predicted demand",
        linewidth=2,
    )
    axis.plot(
        weekly["forecast_date"],
        weekly["baseline_predicted_demand"],
        label="Linear autoregressive baseline total predicted demand",
        linewidth=1.5,
        linestyle="--",
    )
    axis.set_title("Actual vs. Predicted Weekly Demand â€” Chronological Test Period")
    axis.set_xlabel("Forecast week")
    axis.set_ylabel("Total demand across SKUs (units)")
    axis.legend()
    axis.grid(True, alpha=0.3)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(PLOT_PATH, dpi=150)
    plt.close(figure)


def run_evaluation():
    for required_path in (MODEL_PATH, METRICS_PATH):
        if not required_path.is_file():
            raise FileNotFoundError(
                f"Required file {required_path.name} is missing. "
                "Run `python train_model.py` to generate model artifacts."
            )

    model_bundle = joblib.load(MODEL_PATH)
    saved_metrics = load_json(METRICS_PATH)
    metadata = validate_artifacts(model_bundle, saved_metrics)

    frame = load_dataset()
    training, testing = build_holdout(frame, saved_metrics["split_date"])
    training_cutoff = training[DATE_COLUMN].max().date().isoformat()
    recorded_cutoff = metadata.get("last_training_date")
    if training_cutoff != recorded_cutoff:
        raise ValueError(
            "Saved model training cutoff does not match the reconstructed "
            f"training data (model: {recorded_cutoff!r}, data: {training_cutoff!r}). "
            "Regenerate the model and metrics together with `python train_model.py`."
        )
    if testing[DATE_COLUMN].min().date().isoformat() != saved_metrics.get(
        "test_start_date"
    ):
        raise ValueError("Reconstructed test period does not match saved metrics.")
    if testing[DATE_COLUMN].max().date().isoformat() != saved_metrics.get(
        "test_end_date"
    ):
        raise ValueError("Reconstructed test period does not match saved metrics.")

    predictions = write_predictions(testing, training, model_bundle)
    if predictions.empty:
        raise ValueError("No test predictions were produced.")

    model_metrics = calculate_metrics(
        predictions["actual_demand"],
        predictions["ml_predicted_demand"],
    )
    baseline_metrics = calculate_metrics(
        predictions["actual_demand"],
        predictions["baseline_predicted_demand"],
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(PREDICTIONS_PATH, index=False, date_format="%Y-%m-%d")
    create_plot(predictions)

    report = {
        "report_title": "Demand Forecasting Holdout Evaluation",
        "dataset": DATA_PATH.name,
        "product_identifier": PRODUCT_COLUMN,
        "date_column": DATE_COLUMN,
        "target_column": TARGET_COLUMN,
        "evaluation_method": saved_metrics["evaluation"],
        "split_method": saved_metrics["split_method"],
        "split_date": saved_metrics["split_date"],
        "test_period": {
            "start": testing[DATE_COLUMN].min().date().isoformat(),
            "end": testing[DATE_COLUMN].max().date().isoformat(),
            "rows": int(len(testing)),
            "products": int(testing[PRODUCT_COLUMN].nunique()),
        },
        "training_period": {
            "last_training_date": training_cutoff,
            "rows": int(len(training)),
        },
        "metrics": {
            "saved_model": model_metrics,
            "linear_autoregressive_baseline": baseline_metrics,
        },
        "mape_explanation": (
            "MAPE is calculated only for test observations with nonzero actual "
            "demand; zero actuals are excluded because division by zero makes "
            "their percentage error undefined."
        ),
        "saved_training_metrics_for_reference": saved_metrics.get("metrics", {}),
        "artifacts": {
            "test_predictions_csv": PREDICTIONS_PATH.name,
            "actual_vs_predicted_plot": PLOT_PATH.name,
        },
        "leakage_controls": [
            "The saved model is loaded without fitting or retraining it.",
            "The holdout begins at the recorded chronological split date.",
            "The baseline is fitted only on observations before the split date.",
            "Lag and rolling features use earlier observations only; test evaluation is one week ahead at each origin.",
        ],
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Evaluation report: {REPORT_PATH.relative_to(PROJECT_DIR)}")
    print(f"Predictions CSV: {PREDICTIONS_PATH.relative_to(PROJECT_DIR)}")
    print(f"Comparison plot: {PLOT_PATH.relative_to(PROJECT_DIR)}")
    print(
        f"Chronological test period: {report['test_period']['start']} to "
        f"{report['test_period']['end']} ({len(testing)} product-week rows)"
    )
    for name, values in report["metrics"].items():
        mape_text = (
            "undefined (all actuals are zero)"
            if values["mape_percent"] is None
            else f"{values['mape_percent']:.2f}%"
        )
        print(
            f"{name}: MAE={values['mae']:.4f}, "
            f"RMSE={values['rmse']:.4f}, MAPE={mape_text}"
        )


def main():
    try:
        run_evaluation()
    except (
        FileNotFoundError,
        pd.errors.ParserError,
        ValueError,
        KeyError,
        OSError,
    ) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Evaluation failed unexpectedly: {error}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
