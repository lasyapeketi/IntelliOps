
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "processed" / "daily_demand.csv"
MODEL_FILE = ROOT / "modules" / "inventory_optimization" / "inventory_demand_model.joblib"
METRICS_FILE = ROOT / "data" / "processed" / "model_metrics.csv"

def create_features(df):
    df = df.sort_values(["product_id", "Date"]).copy()
    grouped = df.groupby("product_id")["daily_demand"]
    df["lag_1"] = grouped.shift(1)
    df["lag_7"] = grouped.shift(7)
    df["rolling_mean_7"] = df.groupby("product_id")["daily_demand"].transform(
        lambda s: s.shift(1).rolling(7, min_periods=7).mean()
    )
    df["rolling_mean_30"] = df.groupby("product_id")["daily_demand"].transform(
        lambda s: s.shift(1).rolling(30, min_periods=30).mean()
    )
    df["day_of_week"] = df["Date"].dt.dayofweek
    df["month"] = df["Date"].dt.month
    return df

def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Run preprocessing first: {DATA_FILE}")

    df = pd.read_csv(
    DATA_FILE,
    parse_dates=["Date"],
    dtype={"product_id": "string"}
    )
    df = create_features(df)

    features = [
        "lag_1", "lag_7", "rolling_mean_7",
        "rolling_mean_30", "day_of_week", "month"
    ]

    df = df.dropna(subset=features + ["daily_demand"])
    if df.empty:
        raise ValueError("Not enough historical data to create training features.")

    # Use a global date cutoff, so the test period is later than the training period.
    cutoff = df["Date"].quantile(0.8)
    train = df[df["Date"] < cutoff]
    test = df[df["Date"] >= cutoff]

    if train.empty or test.empty:
        raise ValueError("Chronological train/test split produced an empty set.")

    X_train, y_train = train[features], train["daily_demand"]
    X_test, y_test = test[features], test["daily_demand"]

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)
    predictions = np.maximum(0, model.predict(X_test))

    # Baseline uses only the previous seven days, already shifted in create_features.
    baseline = np.maximum(0, test["rolling_mean_7"].to_numpy())

    def metrics(actual, predicted):
        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))
        denominator = np.abs(actual).sum()
        wape = (
            np.abs(actual - predicted).sum() / denominator * 100
            if denominator > 0 else np.nan
        )
        return {"MAE": mae, "RMSE": rmse, "WAPE_percent": wape}

    results = pd.DataFrame([
        {"model": "Moving Average 7-day", **metrics(y_test, baseline)},
        {"model": "Random Forest", **metrics(y_test, predictions)}
    ])

    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": features}, MODEL_FILE)
    results.to_csv(METRICS_FILE, index=False)

    print(f"Training rows: {len(train):,}")
    print(f"Testing rows: {len(test):,}")
    print(f"Train cutoff date: {cutoff.date()}")
    print(results.to_string(index=False))
    print(f"\nSaved model: {MODEL_FILE}")
    print(f"Saved metrics: {METRICS_FILE}")

if __name__ == "__main__":
    main()
