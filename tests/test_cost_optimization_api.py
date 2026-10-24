
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.cost_optimization.api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_cost_optimization_endpoint_success():
    response = client.post(
        "/api/v1/predict/cost_optimization",
        json={
            "use_case": "cost_optimization",
            "request_id": "test-001",
            "input": {
                "resources": [
                    {
                        "resource_id": "WH-001",
                        "total_cost": 200000,
                        "used_capacity": 45,
                        "total_capacity": 100,
                    }
                ],
                "utilization_threshold": 50,
            },
            "options": {"include_explanation": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["use_case"] == "cost_optimization"
    assert body["request_id"] == "test-001"
    assert body["prediction"]["total_cost"] == 200000
    assert body["prediction"]["resources"][0]["flags"] == ["low_utilization"]
    assert body["model"] is None
    assert body["errors"] == []


def test_cost_optimization_endpoint_rejects_wrong_use_case():
    response = client.post(
        "/api/v1/predict/cost_optimization",
        json={
            "use_case": "delivery_delay",
            "input": {
                "resources": [
                    {
                        "resource_id": "WH-001",
                        "total_cost": 200000,
                        "used_capacity": 45,
                        "total_capacity": 100,
                    }
                ]
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["use_case"] == "delivery_delay"
    assert body["prediction"] is None
    assert body["errors"][0]["code"] == "VALIDATION_ERROR"


def test_cost_optimization_endpoint_rejects_empty_resources():
    response = client.post(
        "/api/v1/predict/cost_optimization",
        json={
            "use_case": "cost_optimization",
            "input": {"resources": []},
        },
    )

    assert response.status_code == 422
