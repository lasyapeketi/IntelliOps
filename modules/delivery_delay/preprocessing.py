"""Preprocessing Pipeline for Delivery Delay Prediction.

Handles target variable extraction, feature isolation, anti-leakage checks,
and input validation for training and real-time inference.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd


ALLOWED_SHIPPING_METHODS: Set[str] = {"standard", "express", "same_day", "overnight"}

REQUIRED_INFERENCE_FIELDS: List[str] = [
    "distance_km",
    "shipping_method",
    "promised_delivery_days",
    "historical_avg_delivery_days",
    "order_volume",
]

FORBIDDEN_LEAKAGE_COLUMNS: Set[str] = {
    "actual_delivery_days",
    "actual_delivery_date",
    "actual_delivery_time",
    "actual_transit_days",
    "transit_duration",
}


def create_target_and_features(
    df: pd.DataFrame,
    target_col_name: str = "delayed",
) -> Tuple[pd.DataFrame, pd.Series]:
    """Extract binary classification target 'delayed' and isolate feature set.

    Anti-Leakage Guarantee:
        actual_delivery_days is used ONLY to compute:
            delayed = (actual_delivery_days > promised_delivery_days).astype(int)
        and is immediately dropped. It is NEVER retained in the feature set.

    Args:
        df: Input DataFrame containing cleaned shipment records.
        target_col_name: Name of the resulting binary target series.

    Returns:
        Tuple of (X_features, y_target).

    Raises:
        ValueError: If actual_delivery_days or promised_delivery_days is missing.
    """
    if "actual_delivery_days" not in df.columns:
        raise ValueError("Missing 'actual_delivery_days' required to compute training target.")
    if "promised_delivery_days" not in df.columns:
        raise ValueError("Missing 'promised_delivery_days' required to compute training target.")

    # Compute binary target: 1 = delayed, 0 = on_time
    y = (df["actual_delivery_days"] > df["promised_delivery_days"]).astype(int)
    y.name = target_col_name

    # Isolate feature columns, explicitly dropping forbidden and non-feature columns
    drop_cols = [c for c in df.columns if c in FORBIDDEN_LEAKAGE_COLUMNS or c == "shipment_id"]
    X = df.drop(columns=drop_cols).copy()

    # Safety assertion
    for col in FORBIDDEN_LEAKAGE_COLUMNS:
        assert col not in X.columns, f"Anti-leakage violation: {col} present in feature DataFrame!"

    return X, y


def validate_inference_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate inference dictionary payload against contract constraints.

    Args:
        payload: Dictionary containing input features.

    Returns:
        Validated dictionary with cleaned and typed values.

    Raises:
        ValueError: If required fields are missing, invalid, or forbidden columns are present.
    """
    if not isinstance(payload, dict):
        raise ValueError("Input payload must be a JSON object / Python dictionary.")

    # Anti-leakage guard in inference input
    for forbidden in FORBIDDEN_LEAKAGE_COLUMNS:
        if forbidden in payload:
            raise ValueError(f"Forbidden feature '{forbidden}' detected in input. Actual delivery data must never be provided.")

    # Check required fields
    for field in REQUIRED_INFERENCE_FIELDS:
        if field not in payload or payload[field] is None:
            raise ValueError(f"Missing required field: '{field}'")

    # Validate distance_km
    try:
        distance_km = float(payload["distance_km"])
    except (ValueError, TypeError):
        raise ValueError("Field 'distance_km' must be a valid numeric float.")
    if distance_km <= 0:
        raise ValueError("Field 'distance_km' must be greater than 0.")

    # Validate shipping_method
    shipping_method = str(payload["shipping_method"]).strip().lower()
    if shipping_method not in ALLOWED_SHIPPING_METHODS:
        raise ValueError(
            f"Invalid 'shipping_method': '{shipping_method}'. Allowed: {sorted(list(ALLOWED_SHIPPING_METHODS))}"
        )

    # Validate promised_delivery_days
    try:
        promised_delivery_days = int(payload["promised_delivery_days"])
    except (ValueError, TypeError):
        raise ValueError("Field 'promised_delivery_days' must be a valid integer.")
    if promised_delivery_days < 1:
        raise ValueError("Field 'promised_delivery_days' must be an integer >= 1.")

    # Validate historical_avg_delivery_days
    try:
        historical_avg = float(payload["historical_avg_delivery_days"])
    except (ValueError, TypeError):
        raise ValueError("Field 'historical_avg_delivery_days' must be a valid numeric float.")
    if historical_avg <= 0:
        raise ValueError("Field 'historical_avg_delivery_days' must be greater than 0.")

    # Validate order_volume
    try:
        order_volume = int(payload["order_volume"])
    except (ValueError, TypeError):
        raise ValueError("Field 'order_volume' must be a valid integer.")
    if order_volume < 1:
        raise ValueError("Field 'order_volume' must be an integer >= 1.")

    return {
        "distance_km": distance_km,
        "shipping_method": shipping_method,
        "promised_delivery_days": promised_delivery_days,
        "historical_avg_delivery_days": historical_avg,
        "order_volume": order_volume,
    }
