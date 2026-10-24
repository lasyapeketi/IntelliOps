
import pytest

from modules.cost_optimization.service import analyze_costs


def sample_resources():
    return [
        {
            "resource_id": "R1",
            "total_cost": 1000,
            "used_capacity": 40,
            "total_capacity": 100,
        },
        {
            "resource_id": "R2",
            "total_cost": 500,
            "used_capacity": 80,
            "total_capacity": 100,
        },
    ]


def test_analyzes_cost_and_utilization():
    result = analyze_costs(sample_resources())

    assert result["resource_count"] == 2
    assert result["total_cost"] == 1500
    assert result["average_cost"] == 750
    assert result["resources"][0]["utilization_percent"] == 40
    assert "low_utilization" in result["resources"][0]["flags"]
    assert result["resources"][1]["flags"] == []


def test_cost_history_calculates_variance():
    result = analyze_costs(
        sample_resources(),
        cost_history=[
            {"period": "2026-01", "total_cost": 1000},
            {"period": "2026-02", "total_cost": 1300},
        ],
    )

    latest = result["cost_history_analysis"]["periods"][1]
    assert latest["change_from_previous"] == 300
    assert latest["change_percent"] == 30
    assert "significant_cost_variance" in latest["flags"]


def test_small_cost_change_is_not_flagged():
    result = analyze_costs(
        sample_resources(),
        cost_history=[
            {"period": "2026-01", "total_cost": 1000},
            {"period": "2026-02", "total_cost": 1100},
        ],
    )

    assert result["cost_history_analysis"]["periods"][1]["flags"] == []


def test_one_history_period_warns_insufficient_history():
    result = analyze_costs(
        sample_resources(),
        cost_history=[{"period": "2026-01", "total_cost": 1000}],
    )

    assert result["cost_history_analysis"]["period_count"] == 1
    assert result["cost_history_analysis"]["warnings"]


def test_low_utilization_produces_review_opportunity():
    result = analyze_costs(sample_resources())

    opportunity = result["savings_review_opportunities"][0]
    assert opportunity["resource_id"] == "R1"
    assert opportunity["cost_exposure_for_review"] == 600
    assert opportunity["is_guaranteed_saving"] is False


def test_rejects_negative_cost():
    resources = sample_resources()
    resources[0]["total_cost"] = -1

    with pytest.raises(ValueError, match="cannot be negative"):
        analyze_costs(resources)


def test_rejects_zero_capacity():
    resources = sample_resources()
    resources[0]["total_capacity"] = 0

    with pytest.raises(ValueError, match="greater than zero"):
        analyze_costs(resources)


def test_rejects_empty_resources():
    with pytest.raises(ValueError, match="At least one resource"):
        analyze_costs([])


def test_rejects_duplicate_resource_ids():
    resources = sample_resources()
    resources[1]["resource_id"] = "R1"

    with pytest.raises(ValueError, match="Duplicate resource_id"):
        analyze_costs(resources)


def test_rejects_used_capacity_above_total():
    resources = sample_resources()
    resources[0]["used_capacity"] = 101

    with pytest.raises(ValueError, match="between 0"):
        analyze_costs(resources)


def test_rejects_invalid_utilization_threshold():
    with pytest.raises(ValueError, match="between 0 and 100"):
        analyze_costs(sample_resources(), utilization_threshold=101)


def test_rejects_non_finite_cost():
    resources = sample_resources()
    resources[0]["total_cost"] = float("inf")

    with pytest.raises(ValueError, match="finite"):
        analyze_costs(resources)


def test_rejects_negative_historical_cost():
    with pytest.raises(ValueError, match="cannot be negative"):
        analyze_costs(
            sample_resources(),
            cost_history=[{"period": "2026-01", "total_cost": -10}],
        )


def test_rejects_duplicate_history_period():
    with pytest.raises(ValueError, match="Duplicate cost history period"):
        analyze_costs(
            sample_resources(),
            cost_history=[
                {"period": "2026-01", "total_cost": 100},
                {"period": "2026-01", "total_cost": 110},
            ],
        )


def test_zero_previous_cost_returns_warning():
    result = analyze_costs(
        sample_resources(),
        cost_history=[
            {"period": "2026-01", "total_cost": 0},
            {"period": "2026-02", "total_cost": 100},
        ],
    )

    assert result["cost_history_analysis"]["warnings"]
    assert result["cost_history_analysis"]["periods"][1]["change_percent"] is None
