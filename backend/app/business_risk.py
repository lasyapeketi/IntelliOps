
from typing import Any


RISK_MODEL_NAME = "business-risk-rule-baseline"
RISK_MODEL_VERSION = "0.1.0"


def analyze_business_risk(data: dict[str, Any]) -> dict[str, Any]:
    """
    Assess business risk using transparent, rule-based indicators.

    This is a baseline risk assessment, not a trained machine-learning model.
    External events must be supplied by the caller.
    """

    financial = data.get("financial", {})
    operational = data.get("operational", {})
    external_events = data.get("external_events", [])

    score = 0
    risk_factors: list[dict[str, Any]] = []

    def add_factor(name: str, points: int, detail: str) -> None:
        nonlocal score
        score += points
        risk_factors.append(
            {
                "factor": name,
                "points": points,
                "detail": detail,
            }
        )

    # 1. Financial risk indicators
    revenue_change = financial.get("revenue_change_pct", 0)
    cost_change = financial.get("cost_change_pct", 0)
    cash_runway = financial.get("cash_runway_months", 12)

    if revenue_change <= -20:
        add_factor(
            "revenue_decline",
            25,
            "Revenue decreased by at least 20%.",
        )
    elif revenue_change <= -10:
        add_factor(
            "revenue_decline",
            15,
            "Revenue decreased by at least 10%.",
        )

    if cost_change >= 25:
        add_factor(
            "cost_increase",
            20,
            "Costs increased by at least 25%.",
        )
    elif cost_change >= 10:
        add_factor(
            "cost_increase",
            10,
            "Costs increased by at least 10%.",
        )

    if cash_runway < 3:
        add_factor(
            "low_cash_runway",
            25,
            "Cash runway is below 3 months.",
        )
    elif cash_runway < 6:
        add_factor(
            "low_cash_runway",
            15,
            "Cash runway is below 6 months.",
        )

    # 2. Operational risk indicators
    supplier_disruption = operational.get("supplier_disruption", False)
    delay_rate = operational.get("delivery_delay_rate_pct", 0)
    downtime_hours = operational.get("downtime_hours", 0)

    if supplier_disruption:
        add_factor(
            "supplier_disruption",
            20,
            "A supplier disruption was reported.",
        )

    if delay_rate >= 30:
        add_factor(
            "delivery_delays",
            15,
            "At least 30% of deliveries are delayed.",
        )
    elif delay_rate >= 15:
        add_factor(
            "delivery_delays",
            8,
            "At least 15% of deliveries are delayed.",
        )

    if downtime_hours >= 24:
        add_factor(
            "operational_downtime",
            15,
            "Operational downtime is at least 24 hours.",
        )
    elif downtime_hours >= 8:
        add_factor(
            "operational_downtime",
            8,
            "Operational downtime is at least 8 hours.",
        )

    # 3. External events supplied in the request
    severity_points = {
        "low": 3,
        "medium": 8,
        "high": 15,
        "critical": 20,
    }

    for event in external_events:
        severity = event.get("severity", "low")
        event_name = event.get("name", "Unnamed event")

        # Defensive validation for direct function callers
        if severity not in severity_points:
            raise ValueError(
                f"Unsupported event severity: {severity}"
            )

        add_factor(
            "external_event",
            severity_points[severity],
            f"{event_name}: {severity} severity event reported.",
        )

    # Bound the score to 0–100
    score = min(score, 100)

    # 4. Determine risk level and suggested action
    if score >= 60:
        risk_level = "high"
        recommended_action = (
            "Escalate for prompt review and prepare a risk mitigation plan."
        )
    elif score >= 30:
        risk_level = "medium"
        recommended_action = (
            "Review contributing factors and assign mitigation owners."
        )
    else:
        risk_level = "low"
        recommended_action = (
            "Continue monitoring indicators and update the assessment "
            "when new information becomes available."
        )

    return {
        "label": risk_level,
        "value": score,
        "confidence": None,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "recommended_action": recommended_action,
        "assessment_type": "rule_based_baseline",
    }
