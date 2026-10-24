import pytest
import numpy as np

from modules.sales_revenue_forecasting.preprocessing import (
    validate_and_clean_sales_series,
    extract_time_features,
)
from modules.sales_revenue_forecasting.model import TimeSeriesTrendForecaster
from modules.sales_revenue_forecasting.service import forecast_sales_revenue


def test_validate_and_clean_sales_series_success():
    raw = [12000.0, 13500.0, 12800.0, 14200.0]
    cleaned = validate_and_clean_sales_series(raw)
    assert isinstance(cleaned, np.ndarray)
    assert len(cleaned) == 4
    assert cleaned[0] == 12000.0


def test_validate_and_clean_sales_series_rejects_too_few():
    with pytest.raises(ValueError, match="At least 3 historical sales values are required"):
        validate_and_clean_sales_series([1000.0, 2000.0])


def test_validate_and_clean_sales_series_rejects_negative():
    with pytest.raises(ValueError, match="cannot be negative"):
        validate_and_clean_sales_series([1000.0, -200.0, 1500.0])


def test_validate_and_clean_sales_series_rejects_booleans():
    with pytest.raises(ValueError, match="must be a number, not boolean"):
        validate_and_clean_sales_series([1000.0, True, 1500.0])


def test_validate_and_clean_sales_series_rejects_non_numeric():
    with pytest.raises(ValueError, match="must be a valid number"):
        validate_and_clean_sales_series([1000.0, "abc", 1500.0])


def test_forecaster_fit_known_linear_trend():
    forecaster = TimeSeriesTrendForecaster()
    # y = 100 + 10*t for t=0,1,2,3 -> [100, 110, 120, 130]
    series = np.array([100.0, 110.0, 120.0, 130.0])
    forecaster.fit(series)

    assert round(forecaster.slope, 2) == 10.0
    assert round(forecaster.intercept, 2) == 100.0
    assert round(forecaster.in_sample_mae, 4) == 0.0
    assert round(forecaster.in_sample_rmse, 4) == 0.0


def test_forecaster_predict_horizon_bounds():
    forecaster = TimeSeriesTrendForecaster()
    series = np.array([100.0, 105.0, 112.0, 118.0, 125.0])
    forecaster.fit(series)

    horizon = 3
    preds = forecaster.predict_horizon(horizon_months=horizon)
    assert len(preds) == 3
    for p in preds:
        assert p["upper_bound"] >= p["forecasted_revenue"]
        assert p["forecasted_revenue"] >= p["lower_bound"]
        assert p["lower_bound"] >= 0.0


def test_service_forecast_sales_revenue_success():
    historical = [12000.0, 13500.0, 12800.0, 14200.0, 15100.0, 14800.0]
    response = forecast_sales_revenue(
        historical_sales=historical,
        forecast_horizon_months=3,
        marketing_budget=5000.0,
        seasonality_factor=1.1,
        discount_rate_pct=5.0,
        include_explanation=True,
        request_id="req-test-01",
    )

    assert response["success"] is True
    assert response["use_case"] == "sales_revenue_forecasting"
    assert response["request_id"] == "req-test-01"
    assert response["errors"] == []

    pred = response["prediction"]
    assert pred is not None
    assert pred["total_forecasted_revenue"] > 0
    assert len(pred["forecast_breakdown"]) == 3
    assert pred["metrics"]["observations_count"] == 6
    assert pred["metrics"]["in_sample_mae"] > 0
    assert pred["metrics"]["in_sample_rmse"] > 0

    exp = response["explanation"]
    assert exp is not None
    assert "summary" in exp
    assert len(exp["key_factors"]) >= 3

    model_meta = response["model"]
    assert model_meta is not None
    assert "version" in model_meta


def test_service_forecast_sales_revenue_no_explanation():
    historical = [1000.0, 1100.0, 1200.0]
    response = forecast_sales_revenue(
        historical_sales=historical,
        forecast_horizon_months=2,
        include_explanation=False,
    )

    assert response["success"] is True
    assert response["explanation"] is None


def test_service_rejects_invalid_horizon():
    with pytest.raises(ValueError, match="forecast_horizon_months must be between 1 and 24"):
        forecast_sales_revenue(
            historical_sales=[100.0, 200.0, 300.0],
            forecast_horizon_months=0,
        )


def test_service_rejects_negative_marketing_budget():
    with pytest.raises(ValueError, match="marketing_budget cannot be negative"):
        forecast_sales_revenue(
            historical_sales=[100.0, 200.0, 300.0],
            marketing_budget=-500.0,
        )


def test_service_rejects_invalid_seasonality():
    with pytest.raises(ValueError, match="seasonality_factor must be positive"):
        forecast_sales_revenue(
            historical_sales=[100.0, 200.0, 300.0],
            seasonality_factor=0.0,
        )


def test_service_rejects_invalid_discount():
    with pytest.raises(ValueError, match="discount_rate_pct must be between 0.0 and 100.0"):
        forecast_sales_revenue(
            historical_sales=[100.0, 200.0, 300.0],
            discount_rate_pct=150.0,
        )
