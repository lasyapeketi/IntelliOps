import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.schemas import BusinessProfile
from app.scoring_default import get_default_categories, recommend_default_locations

client = TestClient(app)

def test_default_categories_catalogue():
    categories = get_default_categories()
    assert len(categories) >= 30
    names = [c["name"] for c in categories]
    # Verify categories from prompt requirements exist
    assert any("Commercial Streets" in name for name in names)
    assert any("College Roads" in name for name in names)
    assert any("Bus Stands" in name for name in names)
    assert any("Railway Stations" in name for name in names)
    assert any("Shopping Malls" in name for name in names)
    assert any("IT Parks" in name for name in names)
    assert any("Hospital" in name for name in names)
    assert any("Industrial" in name for name in names)
    assert any("Warehousing" in name for name in names)

def test_default_recommendations_scoring_and_ranking():
    prof = BusinessProfile(
        business_name="Green Leaf Pharmacy",
        category="Pharmacy",
        target_customer="Patients and local residents",
        budget=50000,
        parking_required=False
    )
    res = recommend_default_locations("Pharmacy", prof)
    recs = res["recommendations"]
    assert len(recs) >= 30
    assert all(0 <= r["score"] <= 100 for r in recs)
    # Ranks must be 1 to N in order
    assert [r["rank"] for r in recs[:5]] == [1, 2, 3, 4, 5]
    # For Pharmacy, Hospital / Healthcare and Residential should be ranked near top
    top_categories = [r["name"] for r in recs[:5]]
    assert any("Hospital" in name or "Residential" in name or "Market" in name for name in top_categories)

def test_default_recommendations_budget_warning_and_penalty():
    # Low budget should trigger warnings on premium zones
    low_budget_prof = BusinessProfile(
        category="Restaurant",
        budget=20000  # Below typical mall or CBD rent
    )
    res = recommend_default_locations("Restaurant", low_budget_prof)
    mall = next(r for r in res["recommendations"] if "Shopping Malls" in r["name"])
    assert any("exceed" in w.lower() or "budget" in w.lower() for w in mall["warnings"])

def test_default_recommendations_parking_mandate():
    park_prof = BusinessProfile(
        category="Gym",
        budget=80000,
        parking_required=True
    )
    res = recommend_default_locations("Gym", park_prof)
    bus_stand = next(r for r in res["recommendations"] if "Bus Stands" in r["name"])
    assert any("parking" in w.lower() for w in bus_stand["warnings"])

def test_default_recommendations_api_endpoints():
    # Test GET categories
    get_res = client.get("/api/location/default/categories")
    assert get_res.status_code == 200
    assert get_res.json()["count"] >= 30

    # Test POST recommend
    payload = {
        "business_type": "Restaurant",
        "profile": {
            "business_name": "Spice Route",
            "category": "Restaurant",
            "budget": 75000,
            "target_customer": "Families and food lovers"
        }
    }
    rec_res = client.post("/api/location/default/recommend", json=payload)
    assert rec_res.status_code == 200
    data = rec_res.json()
    assert len(data["recommendations"]) >= 30
    assert data["recommendations"][0]["rank"] == 1
    assert "metadata" in data

    # Test POST compare
    comp_res = client.post("/api/location/default/compare", json=payload)
    assert comp_res.status_code == 200
    assert len(comp_res.json()["recommendations"]) >= 30

    # Test POST scenario
    scenario_payload = dict(payload)
    scenario_payload["business_type"] = "Stationery Store"
    scen_res = client.post("/api/location/default/scenario", json=scenario_payload)
    assert scen_res.status_code == 200
    # For stationery, College Roads or University should be #1 or near top
    top_name = scen_res.json()["recommendations"][0]["name"]
    assert "College" in top_name or "University" in top_name or "Educational" in top_name or "Market" in top_name
