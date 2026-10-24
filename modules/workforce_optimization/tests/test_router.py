
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.workforce_optimization.router import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture
def valid_payload():
    return {
        "use_case": "workforce_optimization",
        "request_id": "req-001",
        "input": {
            "task": {
                "required_skills": ["Python", "SQL"],
                "budget_per_hour": 100,
            },
            "employees": [
                {
                    "employee_id": "E01",
                    "skills": ["Python", "SQL"],
                    "available": True,
                    "current_workload": 20,
                    "max_workload": 100,
                    "hourly_cost": 80,
                },
                {
                    "employee_id": "E02",
                    "skills": ["Python"],
                    "available": True,
                    "current_workload": 10,
                    "max_workload": 100,
                    "hourly_cost": 50,
                },
            ],
        },
        "options": {"include_explanation": True},
    }


def test_successful_prediction_matches_contract(valid_payload):
    response = client.post(
        "/api/v1/predict/workforce_optimization",
        json=valid_payload,
    )

    assert response.status_code == 200

    body = response.json()
    assert set(body) == {
        "success",
        "use_case",
        "request_id",
        "prediction",
        "explanation",
        "model",
        "errors",
    }
    assert body["success"] is True
    assert body["request_id"] == "req-001"
    assert body["prediction"]["recommended_employee"]["employee_id"] == "E01"
    assert body["errors"] == []


def test_wrong_use_case_returns_standard_error(valid_payload):
    valid_payload["use_case"] = "complaint_sentiment"

    response = client.post(
        "/api/v1/predict/workforce_optimization",
        json=valid_payload,
    )

    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["prediction"] is None
    assert body["explanation"] is None
    assert body["model"] is None
    assert body["errors"][0]["code"] == "VALIDATION_ERROR"


def test_missing_required_input_is_rejected(valid_payload):
    del valid_payload["input"]["task"]["required_skills"]

    response = client.post(
        "/api/v1/predict/workforce_optimization",
        json=valid_payload,
    )

    # Pydantic accepts the task dictionary; the service rejects missing skills.
    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["errors"][0]["code"] == "VALIDATION_ERROR"
