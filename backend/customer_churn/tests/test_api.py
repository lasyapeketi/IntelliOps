
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

VALID_INPUT = {
    "SeniorCitizen": 0,
    "tenure": 12,
    "MonthlyCharges": 70.35,
    "gender": "Female",
    "Partner": "Yes",
    "Dependents": "No",
    "PhoneService": "Yes",
    "MultipleLines": "No",
    "InternetService": "DSL",
    "OnlineSecurity": "No",
    "OnlineBackup": "Yes",
    "DeviceProtection": "No",
    "TechSupport": "No",
    "StreamingTV": "No",
    "StreamingMovies": "Yes",
    "Contract": "Month-to-month",
    "PaperlessBilling": "Yes",
    "PaymentMethod": "Electronic check",
    "TotalCharges": 844.2,
}


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_successful_churn_prediction():
    response = client.post(
        "/api/v1/predict/customer_churn",
        json={
            "use_case": "customer_churn",
            "request_id": "pytest-001",
            "input": VALID_INPUT,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["use_case"] == "customer_churn"
    assert body["request_id"] == "pytest-001"
    assert body["prediction"]["label"] in {"Churn", "Stay"}
    assert 0 <= body["prediction"]["churn_probability"] <= 1


def test_missing_features_returns_validation_error():
    response = client.post(
        "/api/v1/predict/customer_churn",
        json={
            "use_case": "customer_churn",
            "request_id": "pytest-invalid-001",
            "input": {},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "VALIDATION_ERROR"


def test_invalid_numeric_value_returns_validation_error():
    invalid_input = {**VALID_INPUT, "tenure": "not-a-number"}

    response = client.post(
        "/api/v1/predict/customer_churn",
        json={
            "use_case": "customer_churn",
            "request_id": "pytest-invalid-002",
            "input": invalid_input,
        },
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"


def test_unknown_use_case_returns_404():
    response = client.post(
        "/api/v1/predict/unknown",
        json={
            "use_case": "unknown",
            "request_id": "pytest-unknown-001",
            "input": {},
        },
    )

    assert response.status_code == 404
    assert response.json()["success"] is False
    assert response.json()["errors"][0]["code"] == "UNKNOWN_USE_CASE"
