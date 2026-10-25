"""Pytest Test Suite for Delivery Delay Prediction Module.

Tests:
- Model artifact loading and metadata verification
- Valid inference requests (delayed and on-time)
- Toggle behavior for include_explanation (true vs. false)
- Structured error handling on missing fields
- Structured error handling on invalid types
- Structured error handling on negative distance_km
- Structured error handling on null/missing values
- Structured error handling on invalid categorical values
- Anti-leakage rejection of actual delivery inputs
- FastAPI HTTP router endpoints (official and alias routes)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.delivery_delay.model import DeliveryDelayModel
from modules.delivery_delay.router import router
from modules.delivery_delay.service import (
    DeliveryDelayService,
    DeliveryDelayValidationError,
)


@pytest.fixture(scope="module")
def api_client():
    """Create a FastAPI test client with delivery-delay router mounted at /api/v1."""
    app = FastAPI(title="IntelliOps Test")
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture(scope="module")
def service():
    """Create DeliveryDelayService instance."""
    return DeliveryDelayService()


# ===========================================================================
# 1. Model Loading Tests
# ===========================================================================

def test_model_loading():
    """Verify that the model artifact loads with required metadata and pipeline."""
    model = DeliveryDelayModel.load()
    assert model is not None
    assert model.model_name == "delivery-delay-model"
    assert model.version == "1.0"
    assert model.estimator is not None
    assert model.feature_pipeline is not None
    assert model.feature_pipeline.is_fitted is True
    assert len(model.top_factors) > 0
    assert len(model.get_top_features(5)) == 5


# ===========================================================================
# 2. Service-Level Unit Tests (Python API)
# ===========================================================================

def test_service_predict_likely_delayed(service):
    """Verify inference for a likely-delayed shipment."""
    delayed_input = {
        "distance_km": 750.0,
        "shipping_method": "standard",
        "promised_delivery_days": 2,
        "historical_avg_delivery_days": 4.5,
        "order_volume": 6,
    }
    result = service.predict(delayed_input, include_explanation=True)

    assert result["label"] == "delayed"
    assert result["value"] == 1
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["key_factors"], list)
    assert len(result["key_factors"]) > 0


def test_service_predict_likely_ontime(service):
    """Verify inference for a likely-on-time shipment."""
    ontime_input = {
        "distance_km": 25.0,
        "shipping_method": "same_day",
        "promised_delivery_days": 1,
        "historical_avg_delivery_days": 0.4,
        "order_volume": 1,
    }
    result = service.predict(ontime_input, include_explanation=True)

    assert result["label"] == "on_time"
    assert result["value"] == 0
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["key_factors"], list)
    assert len(result["key_factors"]) > 0


def test_service_include_explanation_false(service):
    """Verify that key_factors is [] when include_explanation is False."""
    sample_input = {
        "distance_km": 150.0,
        "shipping_method": "express",
        "promised_delivery_days": 2,
        "historical_avg_delivery_days": 1.8,
        "order_volume": 2,
    }
    result = service.predict(sample_input, include_explanation=False)

    assert result["label"] in ["delayed", "on_time"]
    assert result["key_factors"] == []


def test_service_missing_field_raises_structured_error(service):
    """Verify that missing fields raise DeliveryDelayValidationError naming the field."""
    invalid_input = {
        "shipping_method": "standard",
        "promised_delivery_days": 3,
        "historical_avg_delivery_days": 2.5,
        "order_volume": 2,
        # distance_km missing
    }
    with pytest.raises(DeliveryDelayValidationError) as exc_info:
        service.predict(invalid_input)

    assert exc_info.value.field == "input.distance_km"
    assert "distance_km" in exc_info.value.message


def test_service_negative_distance_raises_structured_error(service):
    """Verify that negative distance_km raises DeliveryDelayValidationError."""
    invalid_input = {
        "distance_km": -45.0,
        "shipping_method": "standard",
        "promised_delivery_days": 3,
        "historical_avg_delivery_days": 2.5,
        "order_volume": 2,
    }
    with pytest.raises(DeliveryDelayValidationError) as exc_info:
        service.predict(invalid_input)

    assert exc_info.value.field == "input.distance_km"
    assert "greater than 0" in exc_info.value.message


def test_service_null_value_raises_structured_error(service):
    """Verify that None/null values raise DeliveryDelayValidationError."""
    invalid_input = {
        "distance_km": None,
        "shipping_method": "standard",
        "promised_delivery_days": 3,
        "historical_avg_delivery_days": 2.5,
        "order_volume": 2,
    }
    with pytest.raises(DeliveryDelayValidationError) as exc_info:
        service.predict(invalid_input)

    assert exc_info.value.field == "input.distance_km"


def test_service_invalid_type_raises_structured_error(service):
    """Verify that non-numeric types for numeric fields raise DeliveryDelayValidationError."""
    invalid_input = {
        "distance_km": "non_numeric_distance",
        "shipping_method": "standard",
        "promised_delivery_days": 3,
        "historical_avg_delivery_days": 2.5,
        "order_volume": 2,
    }
    with pytest.raises(DeliveryDelayValidationError) as exc_info:
        service.predict(invalid_input)

    assert exc_info.value.field == "input.distance_km"


def test_service_anti_leakage_rejection(service):
    """Verify that actual delivery information is strictly rejected."""
    leakage_input = {
        "distance_km": 150.0,
        "shipping_method": "standard",
        "promised_delivery_days": 3,
        "historical_avg_delivery_days": 2.5,
        "order_volume": 2,
        "actual_delivery_days": 4.0,  # FORBIDDEN
    }
    with pytest.raises(DeliveryDelayValidationError) as exc_info:
        service.predict(leakage_input)

    assert "actual_delivery_days" in exc_info.value.field


# ===========================================================================
# 3. HTTP FastAPI Endpoint Integration Tests (TestClient)
# ===========================================================================

def test_api_valid_request_success(api_client):
    """Verify successful prediction via POST /api/v1/predict/delivery_delay."""
    payload = {
        "use_case": "delivery_delay",
        "request_id": "req-test-success",
        "input": {
            "distance_km": 500.0,
            "shipping_method": "standard",
            "promised_delivery_days": 3,
            "historical_avg_delivery_days": 3.2,
            "order_volume": 2,
        },
        "options": {"include_explanation": True},
    }
    response = api_client.post("/api/v1/predict/delivery_delay", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["use_case"] == "delivery_delay"
    assert data["request_id"] == "req-test-success"
    assert data["errors"] == []
    assert data["model"]["name"] == "delivery-delay-model"
    assert data["model"]["version"] == "1.0"
    assert data["prediction"]["label"] in ["delayed", "on_time"]
    assert data["prediction"]["value"] in [0, 1]
    assert isinstance(data["explanation"]["key_factors"], list)


def test_api_include_explanation_false(api_client):
    """Verify options.include_explanation = False returns empty key_factors."""
    payload = {
        "use_case": "delivery_delay",
        "request_id": "req-no-expl",
        "input": {
            "distance_km": 500.0,
            "shipping_method": "standard",
            "promised_delivery_days": 3,
            "historical_avg_delivery_days": 3.2,
            "order_volume": 2,
        },
        "options": {"include_explanation": False},
    }
    response = api_client.post("/api/v1/predict/delivery_delay", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["explanation"]["key_factors"] == []


def test_api_missing_field_error(api_client):
    """Verify HTTP 422 with structured error envelope when required field is missing."""
    payload = {
        "use_case": "delivery_delay",
        "request_id": "req-missing-field",
        "input": {
            "shipping_method": "standard",
            "promised_delivery_days": 3,
            "historical_avg_delivery_days": 3.2,
            "order_volume": 2,
            # distance_km missing
        },
    }
    response = api_client.post("/api/v1/predict/delivery_delay", json=payload)
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["prediction"] is None
    assert len(data["errors"]) == 1
    assert data["errors"][0]["code"] == "VALIDATION_ERROR"
    assert data["errors"][0]["field"] == "input.distance_km"


def test_api_negative_distance_error(api_client):
    """Verify HTTP 422 when distance_km is negative."""
    payload = {
        "use_case": "delivery_delay",
        "request_id": "req-negative-dist",
        "input": {
            "distance_km": -250.0,
            "shipping_method": "standard",
            "promised_delivery_days": 3,
            "historical_avg_delivery_days": 3.2,
            "order_volume": 2,
        },
    }
    response = api_client.post("/api/v1/predict/delivery_delay", json=payload)
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["errors"][0]["field"] == "input.distance_km"


def test_api_invalid_shipping_method_error(api_client):
    """Verify HTTP 422 when shipping_method is not in allowed categories."""
    payload = {
        "use_case": "delivery_delay",
        "request_id": "req-bad-shipping",
        "input": {
            "distance_km": 150.0,
            "shipping_method": "unsupported_freight",
            "promised_delivery_days": 3,
            "historical_avg_delivery_days": 3.2,
            "order_volume": 2,
        },
    }
    response = api_client.post("/api/v1/predict/delivery_delay", json=payload)
    assert response.status_code == 422

    data = response.json()
    assert data["success"] is False
    assert data["errors"][0]["field"] == "input.shipping_method"


def test_api_alias_endpoint(api_client):
    """Verify that the alias endpoint POST /api/v1/delivery-delay/predict functions identically."""
    payload = {
        "use_case": "delivery_delay",
        "request_id": "req-alias-test",
        "input": {
            "distance_km": 100.0,
            "shipping_method": "express",
            "promised_delivery_days": 2,
            "historical_avg_delivery_days": 1.5,
            "order_volume": 1,
        },
    }
    response = api_client.post("/api/v1/delivery-delay/predict", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["request_id"] == "req-alias-test"
    assert data["prediction"]["label"] == "on_time"
