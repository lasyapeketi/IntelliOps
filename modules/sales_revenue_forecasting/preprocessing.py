import math
import numpy as np
import pandas as pd


def validate_and_clean_sales_series(sales: list[float]) -> np.ndarray:
    """Validate and clean historical sales time series.

    Ensures values are finite, non-negative, and sufficiently long.
    """
    if not sales or len(sales) < 3:
        raise ValueError("At least 3 historical sales values are required.")

    clean_values = []
    for idx, v in enumerate(sales):
        if isinstance(v, bool):
            raise ValueError(f"Historical sales value at index {idx} must be a number, not boolean.")
        try:
            num = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"Historical sales value at index {idx} must be a valid number.")

        if not math.isfinite(num):
            raise ValueError(f"Historical sales value at index {idx} must be finite.")
        if num < 0.0:
            raise ValueError(f"Historical sales value at index {idx} cannot be negative.")
        clean_values.append(num)

    return np.array(clean_values, dtype=np.float64)


def extract_time_features(n_samples: int) -> np.ndarray:
    """Extract chronological time indices for trend regression.

    Returns:
        X: 2D numpy array of shape (n_samples, 1) containing time indices [0, 1, ..., n-1].
    """
    return np.arange(n_samples, dtype=np.float64).reshape(-1, 1)


def create_lagged_features(
    df: pd.DataFrame,
    target_col: str = "historical_sales",
    max_lag: int = 2,
    rolling_window: int = 3,
) -> pd.DataFrame:
    """Create lagged and rolling features for tabular machine learning training.

    Ensures strictly chronological construction with no future leakage.
    """
    data = df.copy()
    for lag in range(1, max_lag + 1):
        data[f"lag_{lag}"] = data[target_col].shift(lag)

    data[f"rolling_mean_{rolling_window}"] = (
        data[target_col].shift(1).rolling(window=rolling_window, min_periods=1).mean()
    )

    data = data.dropna().reset_index(drop=True)
    return data
