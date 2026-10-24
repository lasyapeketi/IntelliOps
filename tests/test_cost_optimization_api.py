
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.cost_optimization.api import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def sample_request():
    return {
        "use_case": "cost_optimization",
        "request_id": "req-001",
        "input": {
            "resources": [
                {
                    "resource_id": "R1",
                    "total_cost": 1000,
                    "used_capacity": 40,
                    "total_capacity": 100,
                }
            ],
            "cost_history": [
                {"period": "2026-01", "total_cost": 1000},
                {"period": "2026-02", "total_cost": 1400},
            ],
        },
        "options": {},
    }


def test_endpoint_success_includes_analysis():
    response = client.post(
        "/api/v1/predict/cost_optimization",
        json=sample_request(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["request_id"] == "req-001"
    assert body["model"] is None
    assert body["errors"] == []
    assert body["prediction"]["cost_history_analysis"]["period_count"] == 2
    assert body["explanation"]["cost_variance_flags"]


def test_endpoint_rejects_wrong_use_case():
    payload = sample_request()
    payload["use_case"] = "wrong_case"

    response = client.post(
        "/api/v1/predict/cost_optimization",
        json=payload,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["prediction"] is None
    assert body["errors"][0]["field"] == "use_case"


def test_endpoint_rejects_empty_resources():
    payload = sample_request()
    payload["input"]["resources"] = []

    response = client.post(
        "/api/v1/predict/cost_optimization",
        json=payload,
    )

    assert response.status_code == 422


def test_endpoint_rejects_invalid_capacity():
    payload = sample_request()
    payload["input"]["resources"][0]["total_capacity"] = 0

    response = client.post(
        "/api/v1/predict/cost_optimization",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


def test_endpoint_rejects_negative_historical_cost():
    payload = sample_request()
    payload["input"]["cost_history"][0]["total_cost"] = -10

    response = client.post(
        "/api/v1/predict/cost_optimization",
        json=payload,
    )

    assert response.status_code == 422
