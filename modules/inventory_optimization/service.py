
import math
import pandas as pd
import joblib

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_FILE = ROOT / "modules" / "inventory_optimization" / "inventory_demand_model.joblib"
DATA_FILE = ROOT / "data" / "processed" / "daily_demand.csv"

FEATURES = [
    "lag_1",
    "lag_7",
    "rolling_mean_7",
    "rolling_mean_30",
    "day_of_week",
    "month"
]

def load_model():
    if not MODEL_FILE.exists():
        raise FileNotFoundError("Demand model not found. Run the training script first.")
    artifact = joblib.load(MODEL_FILE)
    return artifact["model"]

def forecast_daily_demand(product_id):
    if not DATA_FILE.exists():
        raise FileNotFoundError("Processed daily demand dataset not found.")

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["Date"],
        dtype={"product_id": "string"}
    )

    product = df[df["product_id"] == str(product_id)].sort_values("Date")

    if len(product) < 30:
        raise ValueError("At least 30 days of product history are required.")

    history = product["daily_demand"].to_numpy(dtype=float)
    last_date = product["Date"].max()
    next_date = last_date + pd.Timedelta(days=1)

    features = pd.DataFrame([{
        "lag_1": history[-1],
        "lag_7": history[-7],
        "rolling_mean_7": history[-7:].mean(),
        "rolling_mean_30": history[-30:].mean(),
        "day_of_week": next_date.dayofweek,
        "month": next_date.month
    }], columns=FEATURES)


    model = load_model()
    prediction = float(model.predict(features)[0])
    recent_average = float(history[-7:].mean())

    if prediction <= 0 and recent_average > 0:
        prediction = recent_average

    return max(0.0, prediction)



def optimize_inventory(
    product_id,
    current_stock,
    lead_time_days,
    review_period_days=7,
    safety_stock_days=3
):
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("product_id must be a non-empty string.")

    values = {
        "current_stock": current_stock,
        "lead_time_days": lead_time_days,
        "review_period_days": review_period_days,
        "safety_stock_days": safety_stock_days
    }

    for name, value in values.items():
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a number.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a number.")
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite.")

    if float(current_stock) < 0:
        raise ValueError("current_stock cannot be negative.")
    if float(lead_time_days) < 0:
        raise ValueError("lead_time_days cannot be negative.")
    if float(review_period_days) < 1:
        raise ValueError("review_period_days must be at least 1.")
    if float(safety_stock_days) < 0:
        raise ValueError("safety_stock_days cannot be negative.")

    if float(current_stock) != int(float(current_stock)):
        raise ValueError("current_stock must be a whole number.")
    if float(lead_time_days) != int(float(lead_time_days)):
        raise ValueError("lead_time_days must be a whole number.")
    if float(review_period_days) != int(float(review_period_days)):
        raise ValueError("review_period_days must be a whole number.")
    if float(safety_stock_days) != int(float(safety_stock_days)):
        raise ValueError("safety_stock_days must be a whole number.")

    current_stock = int(current_stock)
    lead_time_days = int(lead_time_days)
    review_period_days = int(review_period_days)
    safety_stock_days = int(safety_stock_days)

    forecast = forecast_daily_demand(product_id)

    reorder_point = forecast * (lead_time_days + safety_stock_days)
    target_stock = forecast * (
        lead_time_days + review_period_days + safety_stock_days
    )
    order_quantity = max(0, math.ceil(target_stock) - current_stock)

    if current_stock <= reorder_point:
        status = "reorder_required"
    elif current_stock < target_stock:
        status = "low_stock"
    else:
        status = "sufficient_stock"

    return {
        "product_id": product_id.strip(),
        "forecast_daily_demand": round(forecast, 2),
        "reorder_point": math.ceil(reorder_point),
        "target_stock": math.ceil(target_stock),
        "current_stock": current_stock,
        "recommended_order_quantity": order_quantity,
        "stock_status": status
    }
