from datetime import datetime, timezone
from typing import Dict, List, Tuple
from .schemas import (
    AnalysisResponse, AnalysisMetadata, BusinessProfile, CandidateLocation,
    FactorResult, LocationAnalysisRequest
)

FACTOR_LABELS = {
    "demand": "Market demand",
    "footfall": "Customer footfall",
    "target_match": "Target-customer match",
    "competition": "Competition",
    "cost_affordability": "Cost affordability",
    "accessibility": "Accessibility",
    "parking": "Parking availability",
    "infrastructure": "Infrastructure",
}

DEFAULT_WEIGHTS = {
    "demand": 0.22, "footfall": 0.15, "target_match": 0.15,
    "competition": 0.12, "cost_affordability": 0.18,
    "accessibility": 0.08, "parking": 0.04, "infrastructure": 0.06,
}

CATEGORY_ADJUSTMENTS = {
    "Restaurant": {"footfall": 1.20, "accessibility": 1.10, "parking": 1.10},
    "Cafe": {"footfall": 1.20, "target_match": 1.10},
    "Grocery Store": {"demand": 1.20, "target_match": 1.10},
    "Clothing Store": {"footfall": 1.15, "target_match": 1.15},
    "Pharmacy": {"accessibility": 1.20, "demand": 1.15},
    "Bakery": {"footfall": 1.15, "target_match": 1.10},
    "Gym": {"target_match": 1.20, "parking": 1.15},
    "Electronics Store": {"target_match": 1.15, "accessibility": 1.10},
    "Salon": {"target_match": 1.15, "footfall": 1.10},
    "Stationery Store": {"demand": 1.10, "target_match": 1.15},
    "Other": {},
}

def normalized_weights(profile: BusinessProfile, overrides: Dict[str, float]) -> Dict[str, float]:
    weights = dict(DEFAULT_WEIGHTS)
    for key, multiplier in CATEGORY_ADJUSTMENTS.get(profile.category, {}).items():
        weights[key] *= multiplier
    for key, value in overrides.items():
        if key not in weights:
            raise ValueError(f"Unknown weight factor: {key}")
        if value < 0:
            raise ValueError(f"Weight for {key} cannot be negative.")
        weights[key] = float(value)
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one factor weight must be greater than zero.")
    return {key: value / total for key, value in weights.items()}

def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))

def _cost_utility(cost: float | None, budget: float) -> float | None:
    if cost is None:
        return None
    # Full utility when total costs use at most 40% of budget, taper to zero at/above budget.
    ratio = cost / budget
    return _clamp(100 * (1 - ratio / 1.0)) if ratio < 1 else 0.0

def _footfall_utility(footfall: float | None) -> float | None:
    if footfall is None:
        return None
    # Log scaling prevents very large estimates from dominating the score.
    import math
    return _clamp(100 * math.log1p(footfall) / math.log1p(5000))

def _factor_values(loc: CandidateLocation, profile: BusinessProfile) -> Dict[str, Tuple[float | bool | None, float | None, str]]:
    cost = None
    if loc.monthly_rent is not None or loc.operating_cost is not None:
        cost = (loc.monthly_rent or 0) + (loc.operating_cost or 0)
    return {
        "demand": (loc.demand, loc.demand, "Higher is better"),
        "footfall": (loc.footfall, _footfall_utility(loc.footfall), "Higher is better; log-scaled"),
        "target_match": (loc.target_match, loc.target_match, "Higher is better"),
        "competition": (loc.competition, None if loc.competition is None else 100 - loc.competition, "Lower competition is better"),
        "cost_affordability": (cost, _cost_utility(cost, profile.budget), "Lower total cost is better"),
        "accessibility": (loc.accessibility, loc.accessibility, "Higher is better"),
        "parking": (loc.parking, None if loc.parking is None else (100.0 if loc.parking else 0.0), "Availability is preferred"),
        "infrastructure": (loc.infrastructure, loc.infrastructure, "Higher is better"),
    }

def analyze(profile: BusinessProfile, locations: List[CandidateLocation], weights: Dict[str, float] | None = None) -> AnalysisResponse:
    if len(locations) < 2:
        raise ValueError("Provide at least two candidate locations to compare.")
    if len({(x.name.strip().lower(), x.area.strip().lower()) for x in locations}) != len(locations):
        raise ValueError("Duplicate candidate locations detected.")
    weights = normalized_weights(profile, weights or {})
    results = []
    for loc in locations:
        raw_factors = _factor_values(loc, profile)
        available_weight = sum(weights[k] for k, (_, utility, _) in raw_factors.items() if utility is not None)
        if available_weight <= 0:
            raise ValueError(f"{loc.name}: not enough data to calculate a suitability score.")
        factor_results = []
        score_numerator = 0.0
        strengths, weaknesses, warnings, next_steps = [], [], [], []
        for key, (raw, utility, direction) in raw_factors.items():
            weight = weights[key]
            contribution = None
            if utility is not None:
                contribution = weight / available_weight * utility
                score_numerator += contribution
            factor_results.append(FactorResult(
                key=key, label=FACTOR_LABELS[key], raw_value=raw,
                utility_score=round(utility, 2) if utility is not None else None,
                weight=round(weight, 4), contribution=round(contribution, 2) if contribution is not None else None,
                direction=direction
            ))
        score = round(score_numerator, 2)
        supplied = sum(1 for _, utility, _ in raw_factors.values() if utility is not None)
        completeness = round(100 * supplied / len(raw_factors), 1)
        utilities = [(key, utility) for key, (_, utility, _) in raw_factors.items() if utility is not None]
        for key, utility in sorted(utilities, key=lambda item: item[1], reverse=True):
            if utility >= 70 and len(strengths) < 3:
                strengths.append(f"{FACTOR_LABELS[key]} is favorable ({utility:.0f}/100).")
        for key, utility in sorted(utilities, key=lambda item: item[1]):
            if utility < 45 and len(weaknesses) < 3:
                weaknesses.append(f"{FACTOR_LABELS[key]} needs attention ({utility:.0f}/100).")
        missing = [FACTOR_LABELS[k] for k, (_, utility, _) in raw_factors.items() if utility is None]
        if missing:
            warnings.append("Not supplied: " + ", ".join(missing) + ". Score is based only on available factors.")
        total_cost = None
        if loc.monthly_rent is not None or loc.operating_cost is not None:
            total_cost = (loc.monthly_rent or 0) + (loc.operating_cost or 0)
            if total_cost > profile.budget:
                warnings.append("Estimated rent plus operating costs exceed the stated budget.")
        if profile.parking_required and loc.parking is False:
            warnings.append("This location does not meet the stated parking requirement.")
        space_miss = False
        if profile.required_space_sqm is not None and loc.space_sqm is not None:
            if loc.space_sqm < profile.required_space_sqm:
                space_miss = True
                warnings.append(f"Available space ({loc.space_sqm:g} m²) is below the required {profile.required_space_sqm:g} m².")
        if completeness < 50:
            warnings.append("Low data completeness; collect more evidence before making a decision.")
        if not strengths:
            strengths.append("No supplied factor reached the favorable threshold; review the detailed comparison.")
        if not weaknesses:
            weaknesses.append("No supplied factor fell below the attention threshold; verify the estimates independently.")
        next_steps = [
            "Verify rent, operating costs, and lease conditions with the property owner.",
            "Validate demand, footfall, and competition using current local evidence.",
        ]
        if loc.parking is None:
            next_steps.append("Confirm parking availability if it matters for the selected business.")
        if profile.preferred_city and loc.city and profile.preferred_city.lower() != loc.city.lower():
            warnings.append("Candidate city differs from the preferred city.")
        classification = "High Suitability" if score >= 75 else "Moderate Suitability" if score >= 50 else "Low Suitability"
        results.append({
            "id": loc.id, "name": loc.name, "area": loc.area, "city": loc.city,
            "score": score, "classification": classification, "data_completeness": completeness,
            "factors": factor_results, "strengths": strengths, "weaknesses": weaknesses,
            "warnings": warnings, "next_steps": next_steps, "cost_total": total_cost,
            "space_sqm": loc.space_sqm,
            "constraint_miss": bool((profile.parking_required and loc.parking is False) or (total_cost is not None and total_cost > profile.budget) or space_miss)
        })
    results.sort(key=lambda r: (r["constraint_miss"], -r["score"], r["name"].lower()))
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank
    from .schemas import LocationRecommendation
    recommendations = [LocationRecommendation(**item) for item in results]
    return AnalysisResponse(
        recommendations=recommendations,
        normalized_weights={k: round(v, 4) for k, v in weights.items()},
        metadata=AnalysisMetadata(
            method="Explainable weighted suitability scoring",
            method_version="1.0.0",
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            locations_evaluated=len(locations),
            disclaimer="Scores are comparative heuristic estimates based on supplied inputs, not probabilities of success. Validate local evidence and review all constraints before investing."
        )
    )
