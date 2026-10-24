import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def valid_payload():
    return {
        "profile": {
            "business_name": "Test Cafe",
            "category": "Cafe",
            "target_customer": "Coffee lovers",
            "budget": 80000,
            "preferred_city": "Test City",
            "required_space_sqm": 80,
            "parking_required": False
        },
        "locations": [
            {
                "id": "loc-1", "name": "Downtown Square", "area": "Center", "city": "Test City",
                "footfall": 1800, "demand": 85, "competition": 45, "monthly_rent": 30000,
                "operating_cost": 20000, "accessibility": 90, "parking": True,
                "infrastructure": 85, "target_match": 80, "space_sqm": 100
            },
            {
                "id": "loc-2", "name": "Suburban Corner", "area": "Suburbs", "city": "Test City",
                "footfall": 900, "demand": 65, "competition": 20, "monthly_rent": 15000,
                "operating_cost": 12000, "accessibility": 70, "parking": True,
                "infrastructure": 65, "target_match": 70, "space_sqm": 90
            }
        ],
        "weights": {}
    }

def test_root_and_favicon():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["module"] == "IntelliOps Business Location Recommendation"
    assert data["status"] == "online"
    assert "docs_url" in data

    fav = client.get("/favicon.ico")
    assert fav.status_code == 204

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["module"] == "business-location-recommendation"

def test_options():
    res = client.get("/api/location/options")
    assert res.status_code == 200
    data = res.json()
    assert "business_categories" in data
    assert "Restaurant" in data["business_categories"]
    assert "default_weights" in data
    assert "demand" in data["default_weights"]

def test_validate_endpoint():
    payload = valid_payload()
    res = client.post("/api/location/validate", json=payload)
    assert res.status_code == 200
    assert res.json()["valid"] is True
    assert res.json()["candidate_count"] == 2

def test_recommend_and_compare_endpoints():
    payload = valid_payload()
    res = client.post("/api/location/recommend", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["recommendations"]) == 2
    assert data["recommendations"][0]["rank"] == 1
    assert "normalized_weights" in data
    assert "metadata" in data
    assert data["metadata"]["method_version"] == "1.0.0"

    compare_res = client.post("/api/location/compare", json=payload)
    assert compare_res.status_code == 200
    assert len(compare_res.json()["recommendations"]) == 2

def test_scenario_endpoint():
    payload = valid_payload()
    # Modify an assumption in scenario
    payload["locations"][1]["demand"] = 95
    res = client.post("/api/location/scenario", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["recommendations"]) == 2

def test_duplicate_locations_rejected():
    payload = valid_payload()
    payload["locations"][1]["name"] = payload["locations"][0]["name"]
    payload["locations"][1]["area"] = payload["locations"][0]["area"]
    res = client.post("/api/location/recommend", json=payload)
    assert res.status_code == 422
    assert "Duplicate candidate locations detected" in res.text

def test_minimum_locations_enforced():
    payload = valid_payload()
    payload["locations"] = payload["locations"][:1]
    res = client.post("/api/location/recommend", json=payload)
    assert res.status_code == 422

def test_csv_upload_success_and_edge_cases():
    # Valid CSV with trailing empty lines
    csv_content = (
        "name,area,city,footfall,demand,competition,monthly_rent,operating_cost,accessibility,parking,infrastructure,target_match,space_sqm\n"
        "Alpha Point,Midtown,Metro City,1500,80,30,25000,15000,85,yes,80,85,120\n"
        "Beta Hub,Harbor,Metro City,2200,90,50,35000,20000,90,no,85,90,150\n"
        "\n"
        "   \n"
    )
    files = {"file": ("test_candidates.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/location/upload", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 2
    assert data["locations"][0]["name"] == "Alpha Point"
    assert data["locations"][0]["parking"] is True
    assert data["locations"][0]["space_sqm"] == 120.0
    assert data["locations"][1]["parking"] is False

def test_csv_upload_rejects_non_csv():
    files = {"file": ("data.txt", io.BytesIO(b"some,data\n"), "text/plain")}
    res = client.post("/api/location/upload", files=files)
    assert res.status_code == 400
    assert "Upload a .csv file" in res.json()["detail"]

def test_csv_upload_rejects_missing_required_headers():
    csv_content = "city,footfall\nMetro,1000\nSub,2000\n"
    files = {"file": ("bad_headers.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/location/upload", files=files)
    assert res.status_code == 422
    assert "must include at least 'name' and 'area'" in res.json()["detail"]

def test_csv_upload_rejects_out_of_range_scores():
    csv_content = (
        "name,area,demand\n"
        "Loc A,Area A,150\n"
        "Loc B,Area B,80\n"
    )
    files = {"file": ("out_of_range.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res = client.post("/api/location/upload", files=files)
    assert res.status_code == 422
    assert "demand must be between 0 and 100" in res.json()["detail"]

def test_csv_upload_handles_latin1_encoding():
    csv_content = (
        "name,area\n"
        "Café Central,Straße 1\n"
        "Bistro Nord,Allee 2\n"
    ).encode("latin-1")
    files = {"file": ("latin1.csv", io.BytesIO(csv_content), "text/csv")}
    res = client.post("/api/location/upload", files=files)
    assert res.status_code == 200
    assert res.json()["count"] == 2

def test_export_endpoint():
    payload = valid_payload()
    res = client.post("/api/location/export", json=payload)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.strip().split("\r\n" if "\r\n" in res.text else "\n")
    assert len(lines) >= 3  # header + 2 locations
    assert "rank,location,area,city,score" in lines[0]
