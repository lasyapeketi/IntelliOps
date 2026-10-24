from typing import Any
import numpy as np

from modules.sales_revenue_forecasting.model import (
    TimeSeriesTrendForecaster,
    load_trained_model_artifact,
)
from modules.sales_revenue_forecasting.preprocessing import validate_and_clean_sales_series

USE_CASE_NAME = "sales_revenue_forecasting"


def forecast_sales_revenue(
    historical_sales: list[float],
    forecast_horizon_months: int = 3,
    marketing_budget: float = 0.0,
    seasonality_factor: float = 1.0,
    discount_rate_pct: float = 0.0,
    include_explanation: bool = False,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Execute sales & revenue forecasting and return the standardized envelope.

    Args:
        historical_sales: Chronological sequence of past sales numbers (>= 3).
        forecast_horizon_months: Forward periods to project (1 to 24).
        marketing_budget: Planned marketing spend across the horizon.
        seasonality_factor: Multiplicative seasonal factor (> 0).
        discount_rate_pct: Planned average discount percentage (0-100).
        include_explanation: Whether to produce narrative key factor breakdown.
        request_id: Optional client-provided request ID.

    Returns:
        Standardized dictionary following the IntelliOps API response contract.
    """
    # 1. Validation & Preprocessing
    clean_series = validate_and_clean_sales_series(historical_sales)

    if forecast_horizon_months < 1 or forecast_horizon_months > 24:
        raise ValueError("forecast_horizon_months must be between 1 and 24.")

    if marketing_budget < 0.0:
        raise ValueError("marketing_budget cannot be negative.")

    if seasonality_factor <= 0.0 or seasonality_factor > 5.0:
        raise ValueError("seasonality_factor must be positive and <= 5.0.")

    if discount_rate_pct < 0.0 or discount_rate_pct > 100.0:
        raise ValueError("discount_rate_pct must be between 0.0 and 100.0.")

    # 2. Fit Time-Series Trend Model
    forecaster = TimeSeriesTrendForecaster()
    forecaster.fit(clean_series)

    # 3. Generate Forecast Breakdown
    breakdown = forecaster.predict_horizon(
        horizon_months=forecast_horizon_months,
        seasonality_factor=seasonality_factor,
        marketing_budget=marketing_budget,
        discount_rate_pct=discount_rate_pct,
    )

    total_forecasted = sum(item["forecasted_revenue"] for item in breakdown)

    # 4. Compute Growth Rate vs Recent Historical Baseline
    recent_window = min(len(clean_series), forecast_horizon_months)
    recent_historical_avg = float(np.mean(clean_series[-recent_window:]))
    forecast_avg = total_forecasted / max(1, forecast_horizon_months)

    if recent_historical_avg > 0:
        growth_rate_pct = round(
            ((forecast_avg - recent_historical_avg) / recent_historical_avg) * 100.0, 2
        )
    else:
        growth_rate_pct = 0.0

    # 5. Build Explanation if Requested
    explanation = None
    if include_explanation:
        key_factors = []

        # Trend Factor
        slope_dir = "upward" if forecaster.slope > 0 else ("downward" if forecaster.slope < 0 else "flat")
        key_factors.append({
            "factor": "Baseline Trend Trajectory",
            "impact": f"{slope_dir.capitalize()} trend of {forecaster.slope:+.2f} per period (in-sample MAE: {forecaster.in_sample_mae:.2f})",
            "type": "statistical_trend",
        })

        # Seasonality
        if abs(seasonality_factor - 1.0) > 0.001:
            diff_pct = (seasonality_factor - 1.0) * 100.0
            key_factors.append({
                "factor": "Seasonality Adjustment",
                "impact": f"{diff_pct:+.1f}% multiplicative adjustment applied to base revenue",
                "type": "scenario_assumption",
            })

        # Marketing Budget
        if marketing_budget > 0.0:
            monthly_mkt = marketing_budget / forecast_horizon_months
            key_factors.append({
                "factor": "Marketing Spend Allocation",
                "impact": f"${marketing_budget:.2f} total (${monthly_mkt:.2f}/month) with estimated incremental revenue contribution",
                "type": "scenario_assumption",
            })

        # Discount Rate
        if discount_rate_pct > 0.0:
            key_factors.append({
                "factor": "Discount Pricing Impact",
                "impact": f"{discount_rate_pct:.1f}% discount rate applied with volume elasticity adjustment",
                "type": "scenario_assumption",
            })

        summary_parts = [
            f"Projected total revenue is ${total_forecasted:,.2f} over {forecast_horizon_months} month(s)",
            f"reflecting a {growth_rate_pct:+.1f}% average shift versus the recent historical period.",
        ]
        if forecaster.slope != 0:
            summary_parts.append(f"Historical trajectory shows a {slope_dir} slope.")

        explanation = {
            "summary": " ".join(summary_parts),
            "key_factors": key_factors,
        }

    # 6. Model Metadata
    artifact = load_trained_model_artifact()
    if artifact:
        model_meta = {
            "name": "Linear Trend Model with Trained Ridge Benchmark",
            "version": "1.0",
            "methodology": "OLS trend on historical inputs with empirical uncertainty intervals; validated against 6-month hold-out benchmark.",
        }
    else:
        model_meta = {
            "name": "Linear Trend Time-Series Forecaster",
            "version": "1.0",
            "methodology": "OLS trend on historical inputs with empirical residual prediction intervals and scenario modifiers.",
        }

    # 7. Final Response Envelope
    return {
        "success": True,
        "use_case": USE_CASE_NAME,
        "request_id": request_id,
        "prediction": {
            "total_forecasted_revenue": round(total_forecasted, 2),
            "projected_growth_rate_pct": growth_rate_pct,
            "forecast_breakdown": breakdown,
            "trend_slope_per_period": round(forecaster.slope, 2),
            "metrics": {
                "in_sample_mae": round(forecaster.in_sample_mae, 2),
                "in_sample_rmse": round(forecaster.in_sample_rmse, 2),
                "observations_count": len(clean_series),
            },
        },
        "explanation": explanation,
        "model": model_meta,
        "errors": [],
    }
