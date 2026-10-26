import pytest
from fastapi.testclient import TestClient

from backend import main as api


@pytest.fixture
def client():
    api._runtime = None
    with TestClient(api.app) as test_client:
        yield test_client
    api._runtime = None


def payload(sku="APP-1000", horizon=4, use_case="demand_forecasting"):
    return {
        "use_case": use_case,
        "request_id": "test-req-001",
        "input": {
            "sku": sku,
            "horizon_weeks": horizon,
        },
        "options": {
            "include_explanation": True,
        },
    }


def test_successful_forecast_returns_standard_envelope(client):
    response = client.post(
        "/api/v1/predict/demand_forecasting",
        json=payload(),
    )

    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "success", "use_case", "request_id", "prediction",
        "explanation", "model", "errors",
    }
    assert body["success"] is True
    assert body["use_case"] == "demand_forecasting"
    assert body["request_id"] == "test-req-001"
    assert body["errors"] == []
    assert body["prediction"]["sku"] == "APP-1000"
    assert len(body["prediction"]["forecasts"]) == 4
    assert body["explanation"] is not None
    assert body["model"] is not None


def test_unknown_sku_returns_structured_error(client):
    response = client.post(
        "/api/v1/predict/demand_forecasting",
        json=payload(sku="UNKNOWN-SKU-XYZ"),
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["request_id"] == "test-req-001"
    assert body["prediction"] is None
    assert body["errors"][0]["code"] == "UNKNOWN_SKU"
    assert body["errors"][0]["field"] == "input.sku"


@pytest.mark.parametrize("horizon", [0, 53, -1])
def test_invalid_horizon_returns_standard_validation_error(client, horizon):
    response = client.post(
        "/api/v1/predict/demand_forecasting",
        json=payload(horizon=horizon),
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["request_id"] == "test-req-001"
    assert body["prediction"] is None
    assert body["errors"][0]["code"] == "VALIDATION_ERROR"


def test_wrong_use_case_is_rejected(client):
    response = client.post(
        "/api/v1/predict/demand_forecasting",
        json=payload(use_case="delivery_delay"),
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "INVALID_USE_CASE"


def test_missing_model_returns_structured_unavailable_error(client, monkeypatch):
    monkeypatch.setattr(api, "MODEL_PATH", api.ROOT_DIR / "missing-test-model.joblib")
    api._runtime = None

    response = client.post(
        "/api/v1/predict/demand_forecasting",
        json=payload(),
    )

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["request_id"] == "test-req-001"
    assert body["prediction"] is None
    assert body["errors"][0]["code"] == "MODEL_UNAVAILABLE"
