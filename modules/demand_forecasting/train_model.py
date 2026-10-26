"""Train and evaluate a leakage-aware weekly demand forecasting model."""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_DIR / "ecommerce_demand_weekly.csv"
MODEL_PATH = PROJECT_DIR / "demand_forecast_model.joblib"
METRICS_PATH = PROJECT_DIR / "test_metrics.json"

# These are the exact date, product, and target columns confirmed in the CSV.
DATE_COLUMN = "date"
PRODUCT_COLUMN = "sku"
TARGET_COLUMN = "true_demand"

BASE_FEATURE_COLUMNS = [
    PRODUCT_COLUMN,
    "week_number",
    "month",
    "year",
    "week_sin",
    "week_cos",
    "lag_1_observation",
    "rolling_mean_4_previous_observations",
    "days_since_previous_observation",
]
NUMERIC_FEATURE_COLUMNS = [
    column for column in BASE_FEATURE_COLUMNS if column != PRODUCT_COLUMN
]


def validate_weekly_dates(dates):
    """Reject malformed or non-weekly date sequences rather than mislabeling them."""
    unique_dates = pd.Series(dates.dropna().unique()).sort_values()
    if unique_dates.empty:
        raise ValueError("No valid dates remain after parsing the date column.")

    weekdays = unique_dates.dt.day_of_week.nunique()
    if weekdays != 1:
        raise ValueError("The date column does not use a consistent weekly weekday.")

    gaps = unique_dates.diff().dropna().dt.days
    if not gaps.empty and (gaps % 7 != 0).any():
        raise ValueError("The date column contains gaps that are not whole weeks.")


def load_dataset(path=DATA_PATH):
    """Load, validate, and clean the observed product-week demand data."""
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")

    dataframe = pd.read_csv(path)
    required_columns = {DATE_COLUMN, PRODUCT_COLUMN, TARGET_COLUMN}
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        names = ", ".join(sorted(missing_columns))
        raise ValueError(f"Dataset is missing required columns: {names}")

    original_rows = len(dataframe)
    dataframe[DATE_COLUMN] = pd.to_datetime(dataframe[DATE_COLUMN], errors="coerce")
    dataframe[TARGET_COLUMN] = pd.to_numeric(
        dataframe[TARGET_COLUMN], errors="coerce"
    )

    valid_rows = (
        dataframe[DATE_COLUMN].notna()
        & dataframe[PRODUCT_COLUMN].notna()
        & dataframe[TARGET_COLUMN].notna()
        & np.isfinite(dataframe[TARGET_COLUMN])
    )
    removed_rows = int((~valid_rows).sum())
    dataframe = dataframe.loc[valid_rows].copy()
    if removed_rows:
        print(
            f"Removed {removed_rows} rows with a missing or invalid date, "
            "product identifier, or demand target."
        )
    if dataframe.empty:
        raise ValueError("No valid product-week observations remain.")

    if (dataframe[TARGET_COLUMN] < 0).any():
        raise ValueError(f"{TARGET_COLUMN} contains negative demand values.")

    # Each row represents one SKU at one week. Without an additional store/channel
    # dimension, duplicate SKU-week rows have ambiguous meaning and must not be summed.
    duplicate_keys = dataframe.duplicated(
        subset=[PRODUCT_COLUMN, DATE_COLUMN], keep=False
    )
    if duplicate_keys.any():
        example = dataframe.loc[
            duplicate_keys, [PRODUCT_COLUMN, DATE_COLUMN]
        ].head(5)
        raise ValueError(
            f"Found {int(duplicate_keys.sum())} rows with duplicate "
            f"{PRODUCT_COLUMN}-{DATE_COLUMN} keys; aggregation is not justified. "
            f"Examples:\n{example.to_string(index=False)}"
        )

    validate_weekly_dates(dataframe[DATE_COLUMN])
    dataframe = dataframe.sort_values(
        [PRODUCT_COLUMN, DATE_COLUMN], kind="stable"
    ).reset_index(drop=True)
    print(
        f"Loaded {len(dataframe)} of {original_rows} rows. "
        f"Product column: {PRODUCT_COLUMN}; date column: {DATE_COLUMN}; "
        f"demand target: {TARGET_COLUMN}."
    )
    print(
        f"Date range: {dataframe[DATE_COLUMN].min().date()} to "
        f"{dataframe[DATE_COLUMN].max().date()}; "
        f"{dataframe[PRODUCT_COLUMN].nunique()} products."
    )
    return dataframe


def add_features(dataframe):
    """Create features using only calendar data and earlier observed demand."""
    result = dataframe.copy()
    grouped_target = result.groupby(PRODUCT_COLUMN, sort=False)[TARGET_COLUMN]

    result["lag_1_observation"] = grouped_target.shift(1)
    result["rolling_mean_4_previous_observations"] = grouped_target.transform(
        lambda values: values.shift(1).rolling(window=4, min_periods=1).mean()
    )
    result["days_since_previous_observation"] = result.groupby(
        PRODUCT_COLUMN, sort=False
    )[DATE_COLUMN].diff().dt.days

    iso_calendar = result[DATE_COLUMN].dt.isocalendar()
    result["week_number"] = iso_calendar.week.astype(int)
    result["month"] = result[DATE_COLUMN].dt.month
    result["year"] = iso_calendar.year.astype(int)
    result["week_sin"] = np.sin(2 * np.pi * result["week_number"] / 52.0)
    result["week_cos"] = np.cos(2 * np.pi * result["week_number"] / 52.0)
    return result


def make_ml_model():
    """Create a tree model with SKU encoding and numeric missing-value handling."""
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "product",
                OneHotEncoder(handle_unknown="ignore"),
                [PRODUCT_COLUMN],
            ),
            (
                "numeric",
                SimpleImputer(strategy="median"),
                NUMERIC_FEATURE_COLUMNS,
            ),
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=150,
                    max_depth=16,
                    min_samples_leaf=5,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def make_baseline_model():
    """Create an autoregressive baseline using only the previous observed demand."""
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("regressor", LinearRegression()),
        ]
    )


def nonnegative_predictions(model, features):
    """Demand cannot be negative, so keep reported and future predictions valid."""
    return np.maximum(model.predict(features), 0.0)


def score_predictions(actual, predicted):
    errors = actual - predicted
    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
    }


def forecast_future_weeks(model_bundle, history, horizon):
    """Recursively forecast future weeks using observed history and prior predictions.

    `history` must contain the CSV's date, SKU, and true_demand columns.
    Each forecast step is appended as a prediction before features for the next
    step are built, so no future actual demand is used.
    """
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
        raise ValueError("horizon must be a positive integer.")

    metadata = model_bundle["metadata"]
    needed = {
        metadata["date_column"],
        metadata["product_column"],
        metadata["target_column"],
    }
    missing = needed.difference(history.columns)
    if missing:
        raise ValueError(
            "Forecast history is missing required columns: "
            + ", ".join(sorted(missing))
        )

    observed = history[list(needed)].copy()
    observed[DATE_COLUMN] = pd.to_datetime(observed[DATE_COLUMN], errors="coerce")
    observed[TARGET_COLUMN] = pd.to_numeric(
        observed[TARGET_COLUMN], errors="coerce"
    )
    valid = (
        observed[DATE_COLUMN].notna()
        & observed[PRODUCT_COLUMN].notna()
        & observed[TARGET_COLUMN].notna()
        & np.isfinite(observed[TARGET_COLUMN])
        & (observed[TARGET_COLUMN] >= 0)
    )
    observed = observed.loc[valid].copy()
    if observed.empty:
        raise ValueError("Forecast history contains no valid observations.")

    if observed.duplicated([PRODUCT_COLUMN, DATE_COLUMN]).any():
        raise ValueError("Forecast history contains duplicate SKU-week observations.")
    validate_weekly_dates(observed[DATE_COLUMN])
    observed = observed.sort_values(
        [PRODUCT_COLUMN, DATE_COLUMN], kind="stable"
    ).reset_index(drop=True)

    products = observed[PRODUCT_COLUMN].unique()
    origin = observed[DATE_COLUMN].max()
    output = []
    model = model_bundle["model"]
    feature_columns = metadata["feature_columns"]

    for week_offset in range(1, horizon + 1):
        forecast_date = origin + pd.Timedelta(days=7 * week_offset)
        features = []
        for product in products:
            product_history = observed.loc[
                observed[PRODUCT_COLUMN] == product
            ].sort_values(DATE_COLUMN)
            previous_targets = product_history[TARGET_COLUMN].to_numpy(dtype=float)
            last_date = product_history[DATE_COLUMN].iloc[-1]
            iso_week = int(forecast_date.isocalendar().week)
            features.append(
                {
                    PRODUCT_COLUMN: product,
                    "week_number": iso_week,
                    "month": forecast_date.month,
                    "year": int(forecast_date.isocalendar().year),
                    "week_sin": np.sin(2 * np.pi * iso_week / 52.0),
                    "week_cos": np.cos(2 * np.pi * iso_week / 52.0),
                    "lag_1_observation": previous_targets[-1],
                    "rolling_mean_4_previous_observations": float(
                        np.mean(previous_targets[-4:])
                    ),
                    "days_since_previous_observation": (
                        forecast_date - last_date
                    ).days,
                }
            )

        feature_frame = pd.DataFrame(features)
        predictions = nonnegative_predictions(
            model, feature_frame[feature_columns]
        )
        new_rows = pd.DataFrame(
            {
                DATE_COLUMN: forecast_date,
                PRODUCT_COLUMN: products,
                TARGET_COLUMN: predictions,
            }
        )
        output.append(
            new_rows.rename(columns={TARGET_COLUMN: "predicted_demand"})
        )
        observed = pd.concat([observed, new_rows], ignore_index=True)

    return pd.concat(output, ignore_index=True)


def train_and_evaluate():
    dataframe = load_dataset()
    featured = add_features(dataframe)

    # The first observation per SKU has no prior demand and cannot be forecast
    # by either autoregressive model; omit it instead of fabricating a lag value.
    featured = featured.dropna(subset=["lag_1_observation"]).copy()
    dates = pd.Series(featured[DATE_COLUMN].unique()).sort_values().reset_index(
        drop=True
    )
    if len(dates) < 5:
        raise ValueError(
            "At least five distinct dates with usable historical features are "
            "needed for a chronological train/test split."
        )

    split_index = int(len(dates) * 0.8)
    split_index = min(max(split_index, 1), len(dates) - 1)
    split_date = dates.iloc[split_index]
    training = featured.loc[featured[DATE_COLUMN] < split_date]
    testing = featured.loc[featured[DATE_COLUMN] >= split_date]
    if training.empty or testing.empty:
        raise ValueError("Chronological split produced an empty training or test set.")

    train_x = training[BASE_FEATURE_COLUMNS]
    test_x = testing[BASE_FEATURE_COLUMNS]
    train_y = training[TARGET_COLUMN].to_numpy(dtype=float)
    test_y = testing[TARGET_COLUMN].to_numpy(dtype=float)

    # The baseline uses only the prior observed demand. The ML model also uses
    # product identity and calendar features; neither sees contemporaneous target
    # values or future actuals.
    baseline = make_baseline_model()
    baseline.fit(
        training[["lag_1_observation"]],
        train_y,
    )
    ml_model = make_ml_model()
    ml_model.fit(train_x, train_y)

    predictions = {
        "autoregressive_linear_baseline": nonnegative_predictions(
            baseline, testing[["lag_1_observation"]]
        ),
        "random_forest": nonnegative_predictions(ml_model, test_x),
    }
    metrics = {
        model_name: score_predictions(test_y, model_predictions)
        for model_name, model_predictions in predictions.items()
    }
    selected_name = min(metrics, key=lambda name: metrics[name]["mae"])
    selected_model = (
        baseline
        if selected_name == "autoregressive_linear_baseline"
        else ml_model
    )
    selected_features = (
        ["lag_1_observation"]
        if selected_name == "autoregressive_linear_baseline"
        else BASE_FEATURE_COLUMNS
    )

    metrics_document = {
        "dataset": DATA_PATH.name,
        "date_column": DATE_COLUMN,
        "product_column": PRODUCT_COLUMN,
        "target_column": TARGET_COLUMN,
        "split_method": "chronological, by date; no random shuffling",
        "evaluation": (
            "Rolling one-week-ahead predictions: prior observed demand is "
            "available at each forecast origin; later test rows may use actual "
            "demand from earlier test weeks, as in repeated weekly operation."
        ),
        "train_rows": int(len(training)),
        "test_rows": int(len(testing)),
        "split_date": split_date.date().isoformat(),
        "test_start_date": testing[DATE_COLUMN].min().date().isoformat(),
        "test_end_date": testing[DATE_COLUMN].max().date().isoformat(),
        "metrics": metrics,
        "selected_model": selected_name,
        "selection_criterion": "lowest test MAE; test metrics are for comparison",
        "notes": [
            "Demand targets with missing or invalid dates, product IDs, or target values are excluded; targets are not imputed.",
            "Duplicate SKU-week rows are rejected because the schema does not establish that summing them is valid.",
            "Future multi-week forecasts must be recursive; forecasted demand is used as the next step's history.",
        ],
    }
    model_bundle = {
        "model": selected_model,
        "metadata": {
            "dataset": DATA_PATH.name,
            "date_column": DATE_COLUMN,
            "product_column": PRODUCT_COLUMN,
            "target_column": TARGET_COLUMN,
            "feature_columns": selected_features,
            "selected_model": selected_name,
            "forecast_horizon": "one week ahead; recursive for multiple weeks",
            "last_training_date": training[DATE_COLUMN].max().date().isoformat(),
        },
    }

    joblib.dump(model_bundle, MODEL_PATH)
    METRICS_PATH.write_text(
        json.dumps(metrics_document, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\nTrain rows: {len(training)}; test rows: {len(testing)}")
    print(f"Chronological split date: {split_date.date()}")
    print("\nTest-set comparison:")
    for model_name, model_metrics in metrics.items():
        print(
            f"  {model_name}: MAE={model_metrics['mae']:.4f}, "
            f"RMSE={model_metrics['rmse']:.4f}"
        )
    print(f"\nSelected model: {selected_name} (lowest test MAE)")
    print(f"Saved model and metadata to: {MODEL_PATH.name}")
    print(f"Saved test metrics to: {METRICS_PATH.name}")
    print(
        "Metrics are test-set results, not a guarantee of future accuracy. "
        "Evaluation is one week ahead at each origin; use the included "
        "forecast_future_weeks function for recursive multi-week forecasts."
    )


def main():
    try:
        train_and_evaluate()
    except (FileNotFoundError, pd.errors.ParserError, ValueError) as error:
        print(f"Training failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
