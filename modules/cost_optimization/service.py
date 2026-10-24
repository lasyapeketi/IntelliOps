
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be numeric.")
    result = float(value)
    if not __import__("math").isfinite(result):
        raise ValueError(f"{field} must be finite.")
    return result


def analyze_costs(
    resources: Sequence[Mapping[str, Any]],
    utilization_threshold: float = 50.0,
    cost_history: Sequence[Mapping[str, Any]] | None = None,
    variance_threshold_percent: float = 20.0,
) -> dict[str, Any]:
    """Analyze resource utilization, cost history, and review opportunities."""

    if not isinstance(resources, Sequence) or isinstance(
        resources, (str, bytes)
    ):
        raise ValueError("resources must be a list of resource objects.")
    if not resources:
        raise ValueError("At least one resource is required.")

    threshold = _number(utilization_threshold, "utilization_threshold")
    if not 0 <= threshold <= 100:
        raise ValueError("utilization_threshold must be between 0 and 100.")

    variance_threshold = _number(
        variance_threshold_percent, "variance_threshold_percent"
    )
    if not 0 <= variance_threshold <= 1000:
        raise ValueError(
            "variance_threshold_percent must be between 0 and 1000."
        )

    results = []
    seen_ids = set()
    total_cost = 0.0
    cost_exposure = 0.0

    for index, resource in enumerate(resources):
        if not isinstance(resource, Mapping):
            raise ValueError(f"Resource at index {index} must be an object.")

        resource_id = resource.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            raise ValueError(f"resources[{index}].resource_id is required.")
        if resource_id in seen_ids:
            raise ValueError(f"Duplicate resource_id: {resource_id}")
        seen_ids.add(resource_id)

        cost = _number(
            resource.get("total_cost"), f"resources[{index}].total_cost"
        )
        used = _number(
            resource.get("used_capacity"),
            f"resources[{index}].used_capacity",
        )
        capacity = _number(
            resource.get("total_capacity"),
            f"resources[{index}].total_capacity",
        )

        if cost < 0:
            raise ValueError(f"resources[{index}].total_cost cannot be negative.")
        if capacity <= 0:
            raise ValueError(
                f"resources[{index}].total_capacity must be greater than zero."
            )
        if not 0 <= used <= capacity:
            raise ValueError(
                f"resources[{index}].used_capacity must be between 0 "
                "and total_capacity."
            )

        utilization = used / capacity * 100
        flags = []
        review_exposure = 0.0

        if utilization < threshold:
            flags.append("low_utilization")
            review_exposure = cost * (1 - utilization / 100)
            cost_exposure += review_exposure

        total_cost += cost
        results.append(
            {
                "resource_id": resource_id,
                "total_cost": round(cost, 2),
                "utilization_percent": round(utilization, 2),
                "unused_capacity_percent": round(100 - utilization, 2),
                "cost_exposure_for_review": round(review_exposure, 2),
                "flags": flags,
            }
        )

    history_results = []
    history_warnings = []
    previous_period = None
    previous_cost = None
    seen_periods = set()

    if cost_history is None:
        cost_history = []

    if not isinstance(cost_history, Sequence) or isinstance(
        cost_history, (str, bytes)
    ):
        raise ValueError("cost_history must be a list of period/cost objects.")

    for index, entry in enumerate(cost_history):
        if not isinstance(entry, Mapping):
            raise ValueError(f"cost_history[{index}] must be an object.")

        period = entry.get("period")
        if not isinstance(period, str) or not period.strip():
            raise ValueError(f"cost_history[{index}].period is required.")
        if period in seen_periods:
            raise ValueError(f"Duplicate cost history period: {period}")
        seen_periods.add(period)

        historical_cost = _number(
            entry.get("total_cost"), f"cost_history[{index}].total_cost"
        )
        if historical_cost < 0:
            raise ValueError(
                f"cost_history[{index}].total_cost cannot be negative."
            )

        change = None
        change_percent = None
        flags = []

        if previous_cost is not None:
            change = historical_cost - previous_cost
            if previous_cost > 0:
                change_percent = change / previous_cost * 100
                if abs(change_percent) >= variance_threshold:
                    flags.append("significant_cost_variance")
            elif historical_cost > 0:
                history_warnings.append(
                    f"Cannot calculate percentage change after zero cost "
                    f"for period {previous_period}."
                )

        history_results.append(
            {
                "period": period,
                "total_cost": round(historical_cost, 2),
                "change_from_previous": (
                    round(change, 2) if change is not None else None
                ),
                "change_percent": (
                    round(change_percent, 2)
                    if change_percent is not None
                    else None
                ),
                "flags": flags,
            }
        )
        previous_period = period
        previous_cost = historical_cost

    if len(history_results) < 2:
        history_warnings.append(
            "At least two historical periods are required to compare costs."
        )

    recommendations = [
        {
            "resource_id": item["resource_id"],
            "reason": "Resource utilization is below the configured threshold.",
            "cost_exposure_for_review": item["cost_exposure_for_review"],
            "action": "Review capacity requirements and cost allocation.",
            "is_guaranteed_saving": False,
        }
        for item in results
        if "low_utilization" in item["flags"]
    ]

    recommendations.sort(
        key=lambda item: item["cost_exposure_for_review"], reverse=True
    )

    return {
        "resource_count": len(results),
        "total_cost": round(total_cost, 2),
        "average_cost": round(total_cost / len(results), 2),
        "utilization_threshold": threshold,
        "resources": results,
        "cost_history_analysis": {
            "period_count": len(history_results),
            "periods": history_results,
            "variance_threshold_percent": variance_threshold,
            "warnings": history_warnings,
        },
        "savings_review_opportunities": recommendations,
        "total_cost_exposure_for_review": round(cost_exposure, 2),
        "notes": [
            "Low utilization is a review flag, not proof of waste.",
            "Cost exposure is an estimate for investigation, not guaranteed savings.",
            "Cost variance flags identify unusual changes for human review.",
            "Historical comparisons use the order of periods supplied by the caller.",
            "No trained machine-learning model is used by this analysis.",
        ],
    }
