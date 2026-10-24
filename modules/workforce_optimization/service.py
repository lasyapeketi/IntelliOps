
from typing import Any

from modules.workforce_optimization.optimizer import rank_employees


USE_CASE = "workforce_optimization"


def optimize_workforce(
    task: dict[str, Any],
    employees: list[dict[str, Any]],
    request_id: str | None = None,
) -> dict[str, Any]:
    """Recommend suitable employees using weighted suitability scoring."""

    if not isinstance(task, dict):
        raise ValueError("task must be a dictionary.")

    if not isinstance(employees, list) or not employees:
        raise ValueError("employees must be a non-empty list.")

    if not task.get("required_skills"):
        raise ValueError("Task must include required_skills.")

    if "budget_per_hour" not in task:
        raise ValueError("Task must include budget_per_hour.")

    ranked_employees = rank_employees(task, employees)

    recommended_employee = (
        ranked_employees[0] if ranked_employees else None
    )

    return {
        "success": True,
        "use_case": USE_CASE,
        "request_id": request_id,
        "prediction": {
            "recommended_employee": recommended_employee,
            "ranked_employees": ranked_employees,
            "eligible_count": len(ranked_employees),
        },
        "explanation": {
            "summary": (
                "Eligible employees are ranked using weighted suitability "
                "scores based on skills, availability, workload, and cost."
            ),
            "key_factors": [
                "Skills match: 40%",
                "Availability: 25%",
                "Remaining workload capacity: 20%",
                "Cost suitability: 15%",
            ],
        },
        "model": {
            "name": "workforce-weighted-scoring",
            "version": "1.0",
        },
        "errors": [],
    }

