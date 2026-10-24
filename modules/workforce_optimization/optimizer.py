
from typing import Any


WEIGHTS = {
    "skills": 0.40,
    "availability": 0.25,
    "workload": 0.20,
    "cost": 0.15,
}


def calculate_suitability(
    required_skills: list[str],
    employee_skills: list[str],
    available: bool,
    current_workload: float,
    max_workload: float,
    hourly_cost: float,
    budget_per_hour: float,
) -> dict[str, Any]:
    """Calculate an employee's suitability for a task."""

    if max_workload <= 0:
        raise ValueError("max_workload must be greater than zero.")

    if current_workload < 0 or current_workload > max_workload:
        raise ValueError(
            "current_workload must be between 0 and max_workload."
        )

    if hourly_cost < 0 or budget_per_hour <= 0:
        raise ValueError(
            "hourly_cost must be non-negative and budget_per_hour "
            "must be greater than zero."
        )

    required = {skill.strip().casefold() for skill in required_skills if skill.strip()}
    employee = {skill.strip().casefold() for skill in employee_skills if skill.strip()}

    if required:
        skills_score = 100 * len(required & employee) / len(required)
    else:
        skills_score = 100.0

    availability_score = 100.0 if available else 0.0

    remaining_capacity = max_workload - current_workload
    workload_score = 100 * remaining_capacity / max_workload

    cost_score = min(100.0, 100 * budget_per_hour / max(hourly_cost, 0.01))
    if hourly_cost == 0:
        cost_score = 100.0

    total_score = (
        skills_score * WEIGHTS["skills"]
        + availability_score * WEIGHTS["availability"]
        + workload_score * WEIGHTS["workload"]
        + cost_score * WEIGHTS["cost"]
    )

    eligible = available and required.issubset(employee) and hourly_cost <= budget_per_hour

    return {
        "skills_score": round(skills_score, 2),
        "availability_score": round(availability_score, 2),
        "workload_score": round(workload_score, 2),
        "cost_score": round(cost_score, 2),
        "suitability_score": round(total_score, 2),
        "eligible": eligible,
    }


def rank_employees(
    task: dict[str, Any],
    employees: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank eligible employees by suitability for a task."""

    ranked = []

    for employee in employees:
        result = calculate_suitability(
            required_skills=task.get("required_skills", []),
            employee_skills=employee.get("skills", []),
            available=employee.get("available", False),
            current_workload=employee.get("current_workload", 0),
            max_workload=employee.get("max_workload", 0),
            hourly_cost=employee.get("hourly_cost", 0),
            budget_per_hour=task.get("budget_per_hour", 0),
        )

        ranked.append({
            "employee_id": employee.get("employee_id"),
            **result,
        })

    return sorted(
        (item for item in ranked if item["eligible"]),
        key=lambda item: item["suitability_score"],
        reverse=True,
    )

