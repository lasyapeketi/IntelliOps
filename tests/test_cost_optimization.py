
import pytest

from modules.cost_optimization.service import analyze_costs


def test_analyzes_resource_cost_and_utilization():
    result = analyze_costs([
        {
            "resource_id": "WH-001",
            "total_cost": 200000,
            "used_capacity": 45,
            "total_capacity": 100,
        }
    ])

    assert result["resource_count"] == 1
    assert result["total_cost"] == 200000.0
    assert result["average_cost"] == 200000.0
    assert result["resources"][0]["utilization_percent"] == 45.0
    assert result["resources"][0]["flags"] == ["low_utilization"]


def test_high_utilization_has_no_low_utilization_flag():
    result = analyze_costs([
        {
            "resource_id": "WH-002",
            "total_cost": 150000,
            "used_capacity": 80,
            "total_capacity": 100,
        }
    ])

    assert result["resources"][0]["utilization_percent"] == 80.0
    assert result["resources"][0]["flags"] == []


def test_rejects_negative_cost():
    with pytest.raises(ValueError, match="cannot be negative"):
        analyze_costs([
            {
                "resource_id": "WH-003",
                "total_cost": -100,
                "used_capacity": 50,
                "total_capacity": 100,
            }
        ])


def test_rejects_zero_capacity():
    with pytest.raises(ValueError, match="greater than zero"):
        analyze_costs([
            {
                "resource_id": "WH-004",
                "total_cost": 100,
                "used_capacity": 0,
                "total_capacity": 0,
            }
        ])


def test_rejects_empty_resource_list():
    with pytest.raises(ValueError, match="At least one resource"):
        analyze_costs([])
