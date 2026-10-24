
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


def analyze_costs(
    resources: Sequence[Mapping[str, Any]],
    utilization_threshold: float = 50.0,
) -> dict[str, Any]:
    """Analyze resource costs and utilization and flag items for review."""

    if not isinstance(resources, Sequence) or isinstance(
        resources, (str, bytes)
    ):
        raise ValueError("resources must be a list of resource objects.")

    if not resources:
        raise ValueError("At least one resource is required.")

    if (
        isinstance(utilization_threshold, bool)
        or not isinstance(utilization_threshold, Real)
        or not 0 <= utilization_threshold <= 100
    ):
        raise ValueError("utilization_threshold must be between 0 and 100.")

    results = []
    seen_ids = set()
    total_cost = 0.0

    for index, resource in enumerate(resources):
        if not isinstance(resource, Mapping):
            raise ValueError(f"Resource at index {index} must be an object.")

        resource_id = resource.get("resource_id")
        cost = resource.get("total_cost")
        used = resource.get("used_capacity")
        capacity = resource.get("total_capacity")

        if not isinstance(resource_id, str) or not resource_id.strip():
            raise ValueError(f"resources[{index}].resource_id is required.")

        if resource_id in seen_ids:
            raise ValueError(f"Duplicate resource_id: {resource_id}")

        seen_ids.add(resource_id)

        for field, value in (
            ("total_cost", cost),
            ("used_capacity", used),
            ("total_capacity", capacity),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
            ):
                raise ValueError(
                    f"resources[{index}].{field} must be numeric."
                )

        if cost < 0:
            raise ValueError(f"resources[{index}].total_cost cannot be negative.")

        if capacity <= 0:
            raise ValueError(
                f"resources[{index}].total_capacity must be greater than zero."
            )

        if used < 0 or used > capacity:
            raise ValueError(
                f"resources[{index}].used_capacity must be between 0 "
                "and total_capacity."
            )

        utilization = used / capacity * 100
        flags = []

        if utilization < utilization_threshold:
            flags.append("low_utilization")

        total_cost += float(cost)

        results.append(
            {
                "resource_id": resource_id,
                "total_cost": float(cost),
                "utilization_percent": round(utilization, 2),
                "flags": flags,
            }
        )

    return {
        "resource_count": len(results),
        "total_cost": round(total_cost, 2),
        "average_cost": round(total_cost / len(results), 2),
        "utilization_threshold": float(utilization_threshold),
        "resources": results,
        "notes": [
            "Low utilization is a review flag, not proof of waste.",
            "No trained machine-learning model is used by this analysis.",
        ],
    }
