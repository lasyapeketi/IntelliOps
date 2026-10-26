import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_DIR / "reports"
PREDICTIONS_PATH = REPORTS_DIR / "test_predictions.csv"
OUTPUT_PATH = REPORTS_DIR / "sku_error_analysis.csv"

def main():
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(
            f"Predictions file not found: {PREDICTIONS_PATH}"
        )

    df = pd.read_csv(PREDICTIONS_PATH)

    required_columns = {
        "sku",
        "actual_demand",
        "ml_predicted_demand",
        "baseline_predicted_demand",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}. "
            f"Available columns: {list(df.columns)}"
        )

    df = df.dropna(
        subset=[
            "sku",
            "actual_demand",
            "ml_predicted_demand",
            "baseline_predicted_demand",
        ]
    ).copy()

    df["absolute_error"] = (
        df["actual_demand"] - df["ml_predicted_demand"]
    ).abs()

    df["baseline_absolute_error"] = (
        df["actual_demand"] - df["baseline_predicted_demand"]
    ).abs()

    df["squared_error"] = (
        df["actual_demand"] - df["ml_predicted_demand"]
    ) ** 2

    results = (
        df.groupby("sku")
        .agg(
            test_observations=("actual_demand", "size"),
            mean_actual_demand=("actual_demand", "mean"),
            mean_predicted_demand=("ml_predicted_demand", "mean"),
            mae=("absolute_error", "mean"),
            baseline_mae=("baseline_absolute_error", "mean"),
            mse=("squared_error", "mean"),
        )
        .reset_index()
    )

    results["rmse"] = np.sqrt(results.pop("mse"))
    results["mae_difference_vs_baseline"] = (
        results["baseline_mae"] - results["mae"]
    )

    results = results.sort_values("mae", ascending=False)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT_PATH, index=False)

    print(f"Products analyzed: {len(results)}")
    print(f"Predictions analyzed: {len(df)}")
    print(f"Results saved to: {OUTPUT_PATH}")

    print("\n10 products with the highest MAE:")
    print(results.head(10).round(3).to_string(index=False))

    print("\n10 products with the lowest MAE:")
    print(
        results.tail(10)
        .sort_values("mae")
        .round(3)
        .to_string(index=False)
    )

    print("\nModel versus baseline across products:")
    print(
        "Products where ML MAE is lower:",
        int((results["mae"] < results["baseline_mae"]).sum()),
    )
    print(
        "Products where baseline MAE is lower:",
        int((results["baseline_mae"] < results["mae"]).sum()),
    )
    print(
        "Products tied:",
        int((results["mae"] == results["baseline_mae"]).sum()),
    )

if __name__ == "__main__":
    main()
