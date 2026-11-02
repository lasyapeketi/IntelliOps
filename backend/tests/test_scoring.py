import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas import BusinessProfile, CandidateLocation
from app.scoring import analyze, normalized_weights

def profile():
    return BusinessProfile(category="Restaurant", budget=100000, parking_required=False)

def loc(id, name, **kwargs):
    base = dict(id=id, name=name, area=name + " Area", city="Test City",
                footfall=1000, demand=75, competition=30, monthly_rent=20000,
                operating_cost=15000, accessibility=80, parking=True,
                infrastructure=70, target_match=75)
    base.update(kwargs)
    return CandidateLocation(**base)

def test_scores_are_bounded_and_ranked():
    result = analyze(profile(), [loc("a", "A"), loc("b", "B", demand=90, footfall=1500)])
    assert len(result.recommendations) == 2
    assert all(0 <= r.score <= 100 for r in result.recommendations)
    assert result.recommendations[0].score >= result.recommendations[1].score

def test_missing_values_are_disclosed():
    result = analyze(profile(), [loc("a", "A", demand=None), loc("b", "B", demand=80)])
    first = next(r for r in result.recommendations if r.name == "A")
    assert any("Not supplied" in warning for warning in first.warnings)
    assert first.data_completeness < 100

def test_weights_normalize():
    weights = normalized_weights(profile(), {"demand": 5, "footfall": 5})
    assert abs(sum(weights.values()) - 1.0) < 1e-9

def test_over_budget_location_is_flagged_and_ranked_after_feasible():
    result = analyze(profile(), [loc("a", "Over", monthly_rent=90000, operating_cost=30000),
                                 loc("b", "Within", monthly_rent=20000, operating_cost=10000)])
    assert result.recommendations[0].name == "Within"
    over = next(r for r in result.recommendations if r.name == "Over")
    assert any("exceed" in warning for warning in over.warnings)

def test_parking_required_constraint():
    prof = BusinessProfile(category="Gym", budget=100000, parking_required=True)
    result = analyze(prof, [loc("a", "NoParking", parking=False),
                           loc("b", "HasParking", parking=True)])
    assert result.recommendations[0].name == "HasParking"
    no_park = next(r for r in result.recommendations if r.name == "NoParking")
    assert any("parking requirement" in w for w in no_park.warnings)

def test_space_required_constraint():
    prof = BusinessProfile(category="Gym", budget=100000, required_space_sqm=200)
    result = analyze(prof, [loc("a", "SmallSpace", space_sqm=120),
                           loc("b", "AdequateSpace", space_sqm=250)])
    assert result.recommendations[0].name == "AdequateSpace"
    small = next(r for r in result.recommendations if r.name == "SmallSpace")
    assert any("Available space (120 m²) is below the required 200 m²" in w for w in small.warnings)

def test_competition_inverse_scoring():
    result = analyze(profile(), [loc("a", "LowComp", competition=10),
                                 loc("b", "HighComp", competition=90)])
    low = next(r for r in result.recommendations if r.name == "LowComp")
    high = next(r for r in result.recommendations if r.name == "HighComp")
    low_comp_f = next(f for f in low.factors if f.key == "competition")
    high_comp_f = next(f for f in high.factors if f.key == "competition")
    assert low_comp_f.utility_score == 90.0
    assert high_comp_f.utility_score == 10.0
    assert low.score > high.score

def test_category_weight_adjustments():
    weights_restaurant = normalized_weights(BusinessProfile(category="Restaurant", budget=50000), {})
    weights_pharmacy = normalized_weights(BusinessProfile(category="Pharmacy", budget=50000), {})
    # Pharmacy emphasizes accessibility more than Restaurant
    assert weights_pharmacy["accessibility"] > weights_restaurant["accessibility"]
    # Restaurant emphasizes footfall more than Pharmacy
    assert weights_restaurant["footfall"] > weights_pharmacy["footfall"]

def test_custom_weight_overrides_and_validation():
    import pytest
    weights = normalized_weights(profile(), {"demand": 0.5, "footfall": 0.5, "cost_affordability": 0.0,
                                            "target_match": 0.0, "competition": 0.0, "accessibility": 0.0,
                                            "parking": 0.0, "infrastructure": 0.0})
    assert abs(weights["demand"] - 0.5) < 1e-6
    assert abs(weights["footfall"] - 0.5) < 1e-6

    with pytest.raises(ValueError, match="Unknown weight factor"):
        normalized_weights(profile(), {"non_existent": 1.0})

    with pytest.raises(ValueError, match="cannot be negative"):
        normalized_weights(profile(), {"demand": -0.5})

def test_insufficient_data_raises_error():
    import pytest
    empty_loc = CandidateLocation(id="empty", name="Empty", area="Void")
    with pytest.raises(ValueError, match="not enough data"):
        analyze(profile(), [empty_loc, loc("b", "B")])
