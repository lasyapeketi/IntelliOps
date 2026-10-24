
import pytest

from modules.workforce_optimization.optimizer import (
    calculate_suitability,
    rank_employees,
)
from modules.workforce_optimization.service import optimize_workforce


@pytest.fixture
def task():
    return {
        "required_skills": ["Python", "SQL"],
        "budget_per_hour": 100,
    }


@pytest.fixture
def employees():
    return [
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
        {
            "employee_id": "E03",
            "skills": ["Python", "SQL"],
            "available": False,
            "current_workload": 10,
            "max_workload": 100,
            "hourly_cost": 60,
        },
    ]


def test_rank_employees_excludes_ineligible(task, employees):
    results = rank_employees(task, employees)

    assert len(results) == 1
    assert results[0]["employee_id"] == "E01"


def test_service_recommends_best_employee(task, employees):
    result = optimize_workforce(task, employees)

    assert result["success"] is True
    assert result["use_case"] == "workforce_optimization"
    assert result["prediction"]["recommended_employee"]["employee_id"] == "E01"


def test_unavailable_employee_is_ineligible():
    result = calculate_suitability(
        required_skills=["Python"],
        employee_skills=["Python"],
        available=False,
        current_workload=10,
        max_workload=100,
        hourly_cost=50,
        budget_per_hour=100,
    )

    assert result["eligible"] is False


def test_invalid_workload_raises_error():
    with pytest.raises(ValueError):
        calculate_suitability(
            required_skills=["Python"],
            employee_skills=["Python"],
            available=True,
            current_workload=120,
            max_workload=100,
            hourly_cost=50,
            budget_per_hour=100,
        )


def test_service_rejects_empty_employee_list(task):
    with pytest.raises(ValueError):
        optimize_workforce(task, [])


def test_service_response_matches_api_contract(task, employees):
    result = optimize_workforce(task, employees, request_id="req-001")

    expected_keys = {
        "success",
        "use_case",
        "request_id",
        "prediction",
        "explanation",
        "model",
        "errors",
    }

    assert set(result.keys()) == expected_keys
    assert result["success"] is True
    assert result["use_case"] == "workforce_optimization"
    assert result["request_id"] == "req-001"
    assert isinstance(result["prediction"], dict)
    assert isinstance(result["explanation"], dict)
    assert isinstance(result["model"], dict)
    assert result["errors"] == []


