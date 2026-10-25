"""Data Loader for Delivery Delay Prediction.

Loads shipment datasets, validates schema, inspects types and value ranges,
reports row counts and missing values per column, and filters out impossible/corrupt
rows safely without crashing.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd


ALLOWED_SHIPPING_METHODS: Set[str] = {"standard", "express", "same_day", "overnight"}

REQUIRED_FEATURE_COLUMNS: List[str] = [
    "distance_km",
    "shipping_method",
    "promised_delivery_days",
    "historical_avg_delivery_days",
    "order_volume",
]

TRAINING_TARGET_COLUMN: str = "actual_delivery_days"


def inspect_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """Inspect dataset size, column presence, and missing values.

    Args:
        df: Input DataFrame.

    Returns:
        Dictionary with row_count, column_count, and missing_values_per_column.
    """
    missing_counts = df.isnull().sum().to_dict()
    report = {
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "missing_values": {str(k): int(v) for k, v in missing_counts.items()},
    }
    return report


def validate_schema(df: pd.DataFrame, is_training: bool = True) -> Tuple[bool, List[str]]:
    """Validate that required columns exist in the DataFrame.

    Args:
        df: DataFrame to validate.
        is_training: If True, requires actual_delivery_days for label creation.

    Returns:
        Tuple of (is_valid, missing_columns).
    """
    required = list(REQUIRED_FEATURE_COLUMNS)
    if is_training:
        required.append(TRAINING_TARGET_COLUMN)

    missing = [col for col in required if col not in df.columns]
    return (len(missing) == 0, missing)


def load_raw_dataset(
    file_path: Optional[str] = None,
    is_training: bool = True,
    verbose: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load, validate, and clean shipment dataset from CSV.

    Rejects rows with impossible or out-of-bound values instead of crashing.

    Args:
        file_path: Path to dataset CSV. Defaults to module synthetic sample.
        is_training: Whether dataset is used for model training/evaluation.
        verbose: If True, prints row counts and missing value diagnostics.

    Returns:
        Tuple of (clean_df, summary_report).

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If essential schema columns are missing.
    """
    if file_path is None:
        file_path = str(Path(__file__).parent / "data" / "synthetic_delivery_delay.csv")

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found at: {file_path}")

    # Read CSV
    raw_df = pd.read_csv(path)
    raw_row_count = len(raw_df)

    # 1. Inspect quality before cleaning
    quality_report = inspect_data_quality(raw_df)

    if verbose:
        print("=" * 60)
        print(f"Loading dataset from: {path.name}")
        print(f"Raw rows loaded: {raw_row_count}")
        print("Missing values per column:")
        for col, count in quality_report["missing_values"].items():
            print(f"  - {col}: {count}")
        print("=" * 60)

    # 2. Schema check
    is_valid, missing_cols = validate_schema(raw_df, is_training=is_training)
    if not is_valid:
        raise ValueError(f"Schema validation failed. Missing required columns: {missing_cols}")

    # 3. Clean and filter invalid/impossible values safely
    df = raw_df.copy()

    # Convert numeric fields safely
    numeric_cols = ["distance_km", "promised_delivery_days", "historical_avg_delivery_days", "order_volume"]
    if is_training:
        numeric_cols.append(TRAINING_TARGET_COLUMN)

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Clean string column
    df["shipping_method"] = df["shipping_method"].astype(str).str.strip().str.lower()

    # Validation masks for valid range checks
    valid_distance = (df["distance_km"] > 0) & df["distance_km"].notnull()
    valid_method = df["shipping_method"].isin(ALLOWED_SHIPPING_METHODS)
    valid_promised = (df["promised_delivery_days"] >= 1) & df["promised_delivery_days"].notnull()
    valid_hist_avg = (df["historical_avg_delivery_days"] > 0) & df["historical_avg_delivery_days"].notnull()
    valid_volume = (df["order_volume"] >= 1) & df["order_volume"].notnull()

    valid_mask = valid_distance & valid_method & valid_promised & valid_hist_avg & valid_volume

    if is_training:
        valid_actual = (df[TRAINING_TARGET_COLUMN] > 0) & df[TRAINING_TARGET_COLUMN].notnull()
        valid_mask = valid_mask & valid_actual

    clean_df = df[valid_mask].copy()

    # Ensure integer types for discrete counts
    clean_df["promised_delivery_days"] = clean_df["promised_delivery_days"].astype(int)
    clean_df["order_volume"] = clean_df["order_volume"].astype(int)

    rejected_count = raw_row_count - len(clean_df)

    summary_report = {
        "file_path": str(path.resolve()),
        "raw_rows": raw_row_count,
        "valid_rows": len(clean_df),
        "rejected_rows": rejected_count,
        "missing_values": quality_report["missing_values"],
    }

    if verbose:
        print(f"Validated clean rows: {len(clean_df)}")
        print(f"Rejected invalid/impossible rows: {rejected_count}")
        print("=" * 60)

    return clean_df, summary_report


if __name__ == "__main__":
    df, report = load_raw_dataset()
