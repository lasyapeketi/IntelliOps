from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.sales_revenue_forecasting.router import router

app = FastAPI(title="IntelliOps Test API")
app.include_router(router)
client = TestClient(app)


def test_api_endpoint_success():
    payload = {
        "use_case": "sales_revenue_forecasting",
        "request_id": "req-001",
        "input": {
            "historical_sales": [12000.0, 13500.0, 12800.0, 14200.0, 15100.0, 14800.0],
            "forecast_horizon_months": 3,
            "marketing_budget": 5000.0,
            "seasonality_factor": 1.1,
            "discount_rate_pct": 5.0,
        },
        "options": {
            "include_explanation": True,
        },
    }

    response = client.post("/api/v1/predict/sales_revenue_forecasting", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["use_case"] == "sales_revenue_forecasting"
    assert data["request_id"] == "req-001"
    assert data["errors"] == []

    # Prediction validation
    pred = data["prediction"]
    assert pred is not None
    assert "total_forecasted_revenue" in pred
    assert "projected_growth_rate_pct" in pred
    assert len(pred["forecast_breakdown"]) == 3
    assert pred["forecast_breakdown"][0]["period"] == "Month 1"
    assert pred["metrics"]["observations_count"] == 6

    # Explanation validation
    exp = data["explanation"]
    assert exp is not None
    assert "summary" in exp
    assert len(exp["key_factors"]) >= 3

    # Model metadata validation
    model = data["model"]
    assert model is not None
    assert "version" in model
    assert "methodology" in model


def test_api_endpoint_defaults_and_no_explanation():
    payload = {
        "use_case": "sales_revenue_forecasting",
        "input": {
            "historical_sales": [10000.0, 11000.0, 12000.0],
        },
    }

    response = client.post("/api/v1/predict/sales_revenue_forecasting", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["request_id"] is None
    assert data["explanation"] is None
    assert len(data["prediction"]["forecast_breakdown"]) == 3  # default horizon = 3


def test_api_endpoint_rejects_mismatched_use_case():
    payload = {
        "use_case": "demand_forecasting",
        "request_id": "req-mismatch",
        "input": {
            "historical_sales": [10000.0, 11000.0, 12000.0],
        },
    }

    response = client.post("/api/v1/predict/sales_revenue_forecasting", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert data["success"] is False
    assert data["use_case"] == "demand_forecasting"
    assert data["request_id"] == "req-mismatch"
    assert data["prediction"] is None
    assert len(data["errors"]) > 0
    assert data["errors"][0]["code"] == "VALIDATION_ERROR"
    assert data["errors"][0]["field"] == "use_case"


def test_api_endpoint_rejects_empty_sales_series():
    payload = {
        "use_case": "sales_revenue_forecasting",
        "input": {
            "historical_sales": [],
        },
    }

    response = client.post("/api/v1/predict/sales_revenue_forecasting", json=payload)
    assert response.status_code == 422


def test_api_endpoint_rejects_negative_sales():
    payload = {
        "use_case": "sales_revenue_forecasting",
        "input": {
            "historical_sales": [10000.0, -500.0, 12000.0],
        },
    }

    response = client.post("/api/v1/predict/sales_revenue_forecasting", json=payload)
    assert response.status_code == 422


def test_api_endpoint_rejects_out_of_range_horizon():
    payload = {
        "use_case": "sales_revenue_forecasting",
        "input": {
            "historical_sales": [10000.0, 11000.0, 12000.0],
            "forecast_horizon_months": 50,
        },
    }

    response = client.post("/api/v1/predict/sales_revenue_forecasting", json=payload)
    assert response.status_code == 422


def test_api_endpoint_rejects_negative_marketing():
    payload = {
        "use_case": "sales_revenue_forecasting",
        "input": {
            "historical_sales": [10000.0, 11000.0, 12000.0],
            "marketing_budget": -100.0,
        },
    }

    response = client.post("/api/v1/predict/sales_revenue_forecasting", json=payload)
    assert response.status_code == 422
