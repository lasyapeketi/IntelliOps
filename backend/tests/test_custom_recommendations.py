import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_minimal_two_column_upload_and_recommendation():
    # Prompt Section 4.2 illustrative example
    csv_data = (
        "Business Type,Location Name\n"
        "Restaurant,Market Road\n"
        "Restaurant,College Road\n"
        "Restaurant,Main Road\n"
        "Restaurant,Market Road\n"
        "Pharmacy,Hospital Area\n"
        "Pharmacy,Residential Area\n"
        "Stationery Shop,College Road\n"
    )
    files = {"file": ("minimal.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    upload_res = client.post("/api/location/custom/upload", files=files)
    assert upload_res.status_code == 200
    summary = upload_res.json()["summary"]
    assert summary["accepted_rows"] == 7
    assert summary["rejected_rows"] == 0
    assert "Restaurant" in summary["available_business_types"]
    assert "Pharmacy" in summary["available_business_types"]
    assert "Stationery Shop" in summary["available_business_types"]
    assert summary["unique_locations_count"] >= 4

    dataset_id = summary["dataset_id"]

    # Recommend for Restaurant
    rec_payload = {
        "dataset_id": dataset_id,
        "selected_business_type": "Restaurant"
    }
    rec_res = client.post("/api/location/custom/recommend", json=rec_payload)
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    recs = rec_data["recommendations"]
    assert len(recs) == 3  # Market Road (2), College Road (1), Main Road (1)
    
    # Market Road appeared 2 times vs 1 for others, so it must be ranked #1
    assert recs[0]["location_name"] == "Market Road"
    assert recs[0]["occurrence_count"] == 2
    assert recs[0]["rank"] == 1
    assert recs[0]["association_percentage"] == 50.0  # 2 out of 4 restaurant records

    # College Road should indicate co-location with Stationery Shop
    college = next(r for r in recs if r["location_name"] == "College Road")
    assert "Stationery Shop" in college["co_located_business_types"]

def test_upload_with_additional_dynamic_columns():
    csv_data = (
        "Business Type,Location Name,Zone,Daily Footfall,Monthly Rent,Customer Rating\n"
        "Cafe,Downtown Core,A,2500,35000,4.8\n"
        "Cafe,Waterfront Promenade,B,1800,28000,4.6\n"
        "Cafe,Suburban Mall,C,3200,45000,4.5\n"
        "Bakery,Downtown Core,A,2400,34000,4.7\n"
    )
    files = {"file": ("enriched.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res = client.post("/api/location/custom/upload", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["summary"]["accepted_rows"] == 4
    # Column types inferred
    col_names = [c["name"] for c in data["summary"]["columns"]]
    assert "Daily Footfall" in col_names
    assert "Monthly Rent" in col_names

    dataset_id = data["summary"]["dataset_id"]
    rec_res = client.post("/api/location/custom/recommend", json={
        "dataset_id": dataset_id,
        "selected_business_type": "Cafe"
    })
    assert rec_res.status_code == 200
    recs = rec_res.json()["recommendations"]
    assert len(recs) == 3
    # Check that numeric metrics are captured
    assert "Monthly Rent" in recs[0]["numeric_metrics"]
    assert "Daily Footfall" in recs[0]["numeric_metrics"]

def test_missing_mandatory_business_type_column():
    csv_data = "Location Name,Footfall\nMarket Road,1000\nCollege Road,2000\n"
    files = {"file": ("missing_bt.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res = client.post("/api/location/custom/upload", files=files)
    assert res.status_code == 422
    assert "Missing required mandatory column" in res.json()["detail"]
    assert "'Business Type'" in res.json()["detail"]

def test_missing_mandatory_location_name_column():
    csv_data = "Business Type,Footfall\nRestaurant,1000\nPharmacy,2000\n"
    files = {"file": ("missing_loc.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res = client.post("/api/location/custom/upload", files=files)
    assert res.status_code == 422
    assert "Missing required mandatory column" in res.json()["detail"]
    assert "'Location Name'" in res.json()["detail"]

def test_rows_with_empty_mandatory_fields_are_counted_as_rejected():
    csv_data = (
        "Business Type,Location Name\n"
        "Restaurant,Market Road\n"
        ",College Road\n"         # Missing business type
        "Restaurant,\n"             # Missing location name
        "Restaurant,Main Road\n"
    )
    files = {"file": ("some_bad_rows.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    res = client.post("/api/location/custom/upload", files=files)
    assert res.status_code == 200
    summary = res.json()["summary"]
    assert summary["accepted_rows"] == 2
    assert summary["rejected_rows"] == 2
    assert any("Row 3" in r for r in summary["rejected_reasons"])
    assert any("Row 4" in r for r in summary["rejected_reasons"])

def test_custom_scenario_evaluation():
    csv_data = (
        "Business Type,Location Name,Monthly Rent\n"
        "Gym,North Sector,40000\n"
        "Gym,South Sector,70000\n"
        "Gym,East Sector,30000\n"
    )
    files = {"file": ("gyms.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    upload_res = client.post("/api/location/custom/upload", files=files)
    dataset_id = upload_res.json()["summary"]["dataset_id"]

    # Scenario with budget constraint
    scen_payload = {
        "dataset_id": dataset_id,
        "selected_business_type": "Gym",
        "budget_filter": 50000  # South Sector (70000) exceeds budget
    }
    scen_res = client.post("/api/location/custom/scenario", json=scen_payload)
    assert scen_res.status_code == 200
    recs = scen_res.json()["recommendations"]
    south = next(r for r in recs if r["location_name"] == "South Sector")
    assert any("exceeds" in w.lower() or "budget" in w.lower() for w in south["warnings"])

def test_template_download_and_export():
    # Template minimal
    min_res = client.get("/api/location/custom/template?type=minimal")
    assert min_res.status_code == 200
    assert "Business Type,Location Name" in min_res.text

    # Template full
    full_res = client.get("/api/location/custom/template?type=full")
    assert full_res.status_code == 200
    assert "Business Type,Location Name,City" in full_res.text

    # Export
    csv_data = (
        "Business Type,Location Name\n"
        "Clinic,Green Park\n"
        "Clinic,Blue Ridge\n"
    )
    files = {"file": ("clinics.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    up = client.post("/api/location/custom/upload", files=files)
    dataset_id = up.json()["summary"]["dataset_id"]

    export_res = client.post("/api/location/custom/export", json={
        "dataset_id": dataset_id,
        "selected_business_type": "Clinic"
    })
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    assert "rank,location_name,business_type,score" in export_res.text

def test_xlsx_file_upload_and_recommendation():
    import zipfile
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as z:
        z.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>''')
        z.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
        z.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>''')
        z.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>''')
        sheet_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr"><is><t>Business Type</t></is></c>
      <c r="B1" t="inlineStr"><is><t>Location Name</t></is></c>
      <c r="C1" t="inlineStr"><is><t>Footfall</t></is></c>
    </row>
    <row r="2">
      <c r="A2" t="inlineStr"><is><t>Bookstore</t></is></c>
      <c r="B2" t="inlineStr"><is><t>Campus Gate</t></is></c>
      <c r="C2"><v>1800</v></c>
    </row>
    <row r="3">
      <c r="A3" t="inlineStr"><is><t>Bookstore</t></is></c>
      <c r="B3" t="inlineStr"><is><t>Metro Promenade</t></is></c>
      <c r="C3"><v>2600</v></c>
    </row>
  </sheetData>
</worksheet>'''
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    files = {"file": ("sample_data.xlsx", io.BytesIO(bio.getvalue()), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    up_res = client.post("/api/location/custom/upload", files=files)
    assert up_res.status_code == 200
    data = up_res.json()
    assert data["summary"]["accepted_rows"] == 2
    assert "Bookstore" in data["summary"]["available_business_types"]

    # Recommend from XLSX
    rec_res = client.post("/api/location/custom/recommend", json={
        "dataset_id": data["summary"]["dataset_id"],
        "selected_business_type": "Bookstore"
    })
    assert rec_res.status_code == 200
    assert len(rec_res.json()["recommendations"]) == 2

