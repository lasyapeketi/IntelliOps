import csv
import io
import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from .schemas import (
    AnalysisResponse, BUSINESS_CATEGORIES, CandidateLocation,
    LocationAnalysisRequest, ScenarioRequest,
    DefaultAnalysisRequest, DefaultAnalysisResponse, DefaultScenarioRequest,
    CustomAnalysisRequest, CustomAnalysisResponse, CustomScenarioRequest,
    CustomUploadResponse
)
from .scoring import analyze, DEFAULT_WEIGHTS
from .scoring_default import get_default_categories, recommend_default_locations
from .scoring_custom import (
    parse_and_validate_dataset, recommend_custom_locations, DATASET_CACHE
)

app = FastAPI(
    title="IntelliOps Business Location Recommendation API",
    description="Explainable decision-support and data-driven candidate-location recommendation API.",
    version="2.0.0",
)

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in origins if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

@app.get("/", include_in_schema=False)
def root():
    return {
        "module": "IntelliOps Business Location Recommendation",
        "status": "online",
        "version": "2.0.0",
        "methods_supported": [
            "Default Recommendations (Knowledge-Base MCDA)",
            "Based on Your Data Input (User Dataset Association & Utility Engine)"
        ],
        "docs_url": "/docs",
        "health_url": "/api/health"
    }

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.get("/api/health")
def health():
    return {"status": "ok", "module": "business-location-recommendation", "version": "2.0.0"}

@app.get("/api/location/options")
def options():
    return {
        "business_categories": BUSINESS_CATEGORIES,
        "default_weights": DEFAULT_WEIGHTS,
        "default_location_categories": [c["name"] for c in get_default_categories()]
    }


# ===========================================================================
# 1. Section 4.1: Default Recommendations Endpoints
# ===========================================================================

@app.get("/api/location/default/categories")
def default_categories():
    """Return the extensible catalogue of 31+ location categories with metadata."""
    return {"categories": get_default_categories(), "count": len(get_default_categories())}

@app.post("/api/location/default/recommend", response_model=DefaultAnalysisResponse)
def recommend_default(payload: DefaultAnalysisRequest):
    """Generate default location recommendations based on business type and profile."""
    try:
        return recommend_default_locations(
            business_type=payload.business_type,
            profile=payload.profile,
            weights=payload.weights,
            environments=payload.environments
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post("/api/location/default/compare", response_model=DefaultAnalysisResponse)
def compare_default(payload: DefaultAnalysisRequest):
    """Compare candidate categories for default recommendations."""
    return recommend_default(payload)

@app.post("/api/location/default/scenario", response_model=DefaultAnalysisResponse)
def scenario_default(payload: DefaultScenarioRequest):
    """Run what-if scenario on default recommendations."""
    return recommend_default(payload)


# ===========================================================================
# 2. Section 4.2: Based on Your Data Input Endpoints
# ===========================================================================

@app.post("/api/location/custom/upload", response_model=CustomUploadResponse)
async def upload_custom_dataset(file: UploadFile = File(...)):
    """Upload and inspect a user-provided dataset (CSV or XLSX).
    
    Mandatory columns: 'Business Type' and 'Location Name'.
    All other columns are optional and dynamically accepted.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please select a file to upload.")
    
    fn_lower = file.filename.lower()
    if not (fn_lower.endswith(".csv") or fn_lower.endswith(".xlsx") or fn_lower.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Upload a CSV (.csv) or Excel (.xlsx) file.")

    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Dataset file must be 10 MB or smaller.")

    try:
        parsed = parse_and_validate_dataset(raw, file.filename)
        return parsed
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Error processing dataset: {exc}") from exc

@app.post("/api/location/custom/recommend", response_model=CustomAnalysisResponse)
def recommend_custom(payload: CustomAnalysisRequest):
    """Generate recommendations from uploaded user dataset for a selected business type."""
    try:
        return recommend_custom_locations(
            dataset_id=payload.dataset_id,
            rows=payload.rows,
            selected_business_type=payload.selected_business_type,
            min_occurrences=payload.min_occurrences,
            weight_frequency=payload.weight_frequency,
            weight_metrics=payload.weight_metrics,
            budget_filter=payload.budget_filter,
            metric_overrides=payload.metric_overrides
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post("/api/location/custom/compare", response_model=CustomAnalysisResponse)
def compare_custom(payload: CustomAnalysisRequest):
    """Compare locations from user-uploaded dataset."""
    return recommend_custom(payload)

@app.post("/api/location/custom/scenario", response_model=CustomAnalysisResponse)
def scenario_custom(payload: CustomScenarioRequest):
    """Run what-if scenario on user dataset recommendations."""
    return recommend_custom(payload)

@app.get("/api/location/custom/template")
def download_template(type: str = Query("minimal", pattern="^(minimal|full)$")):
    """Download CSV template for user data input."""
    stream = io.StringIO()
    writer = csv.writer(stream)
    if type == "minimal":
        writer.writerow(["Business Type", "Location Name"])
        writer.writerow(["Restaurant", "Market Road"])
        writer.writerow(["Restaurant", "College Road"])
        writer.writerow(["Restaurant", "Main Road"])
        writer.writerow(["Pharmacy", "Hospital Area"])
        writer.writerow(["Pharmacy", "Residential Area"])
        writer.writerow(["Stationery Shop", "College Road"])
        filename = "intelliops_minimal_template.csv"
    else:
        writer.writerow(["Business Type", "Location Name", "City", "Footfall", "Demand", "Rent", "Operating Cost", "Competition", "Customer Rating"])
        writer.writerow(["Restaurant", "Market Road", "Metropolis", 2200, 85, 32000, 18000, 45, 4.6])
        writer.writerow(["Restaurant", "College Road", "Metropolis", 1900, 78, 24000, 14000, 35, 4.4])
        writer.writerow(["Restaurant", "Downtown Plaza", "Metropolis", 3100, 92, 55000, 25000, 60, 4.8])
        writer.writerow(["Pharmacy", "Hospital Area", "Metropolis", 1600, 90, 28000, 12000, 25, 4.7])
        writer.writerow(["Pharmacy", "Residential Colony", "Metropolis", 1100, 75, 18000, 9000, 15, 4.3])
        writer.writerow(["Stationery Shop", "College Road", "Metropolis", 1800, 88, 22000, 10000, 30, 4.5])
        filename = "intelliops_sample_dataset.csv"

    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.post("/api/location/custom/export")
def export_custom_results(payload: CustomAnalysisRequest):
    """Export custom dataset recommendations as CSV."""
    try:
        results = recommend_custom_locations(
            dataset_id=payload.dataset_id,
            rows=payload.rows,
            selected_business_type=payload.selected_business_type,
            min_occurrences=payload.min_occurrences,
            weight_frequency=payload.weight_frequency,
            weight_metrics=payload.weight_metrics,
            budget_filter=payload.budget_filter,
            metric_overrides=payload.metric_overrides
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow([
        "rank", "location_name", "business_type", "score", "classification",
        "occurrence_count", "association_percentage", "co_located_businesses",
        "strengths", "weaknesses", "warnings"
    ])
    for r in results["recommendations"]:
        writer.writerow([
            r["rank"], r["location_name"], r["business_type"], r["score"], r["classification"],
            r["occurrence_count"], f"{r['association_percentage']}%",
            " | ".join(r["co_located_business_types"]),
            " | ".join(r["strengths"]), " | ".join(r["weaknesses"]), " | ".join(r["warnings"])
        ])

    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="intelliops-data-driven-recommendations.csv"'}
    )


# ===========================================================================
# 3. Existing Baseline Multi-Factor Endpoints (Preserved for Compatibility)
# ===========================================================================

@app.post("/api/location/validate")
def validate(payload: LocationAnalysisRequest):
    return {
        "valid": True,
        "candidate_count": len(payload.locations),
        "messages": ["Inputs passed schema validation. Scores remain estimates based on supplied data."]
    }

@app.post("/api/location/recommend", response_model=AnalysisResponse)
def recommend(payload: LocationAnalysisRequest):
    try:
        return analyze(payload.profile, payload.locations, payload.weights)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post("/api/location/compare", response_model=AnalysisResponse)
def compare(payload: LocationAnalysisRequest):
    return recommend(payload)

@app.post("/api/location/scenario", response_model=AnalysisResponse)
def scenario(payload: ScenarioRequest):
    try:
        return analyze(payload.profile, payload.locations, payload.weights)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post("/api/location/upload")
async def upload_locations(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV file must be 5 MB or smaller.")
    try:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV needs a header row.")
        aliases = {h.strip().lower(): h for h in reader.fieldnames if h}
        required = {"name", "area"}
        if not required.issubset(aliases):
            raise ValueError("CSV must include at least 'name' and 'area' columns.")
        def get(row, key, default=None):
            original = aliases.get(key)
            return row.get(original, default) if original else default
        def num(value, field):
            if value is None or str(value).strip() == "":
                return None
            result = float(value)
            if result < 0:
                raise ValueError(f"{field} must be non-negative.")
            return result
        def score(value, field):
            result = num(value, field)
            if result is not None and result > 100:
                raise ValueError(f"{field} must be between 0 and 100.")
            return result
        locations = []
        for i, row in enumerate(reader, start=1):
            if not row or all(v is None or not str(v).strip() for v in row.values()):
                continue
            name, area = (get(row, "name", "") or "").strip(), (get(row, "area", "") or "").strip()
            if not name or not area:
                raise ValueError(f"Row {i}: name and area are required.")
            parking_raw = get(row, "parking")
            parking = None
            if parking_raw is not None and str(parking_raw).strip() != "":
                v = str(parking_raw).strip().lower()
                if v not in {"true", "false", "yes", "no", "1", "0"}:
                    raise ValueError(f"Row {i}: parking must be true/false, yes/no, or 1/0.")
                parking = v in {"true", "yes", "1"}
            locations.append(CandidateLocation(
                id=f"csv-{len(locations) + 1}", name=name, area=area, city=get(row, "city", "") or "",
                footfall=num(get(row, "footfall"), "footfall"),
                demand=score(get(row, "demand"), "demand"),
                competition=score(get(row, "competition"), "competition"),
                monthly_rent=num(get(row, "monthly_rent"), "monthly_rent"),
                operating_cost=num(get(row, "operating_cost"), "operating_cost"),
                accessibility=score(get(row, "accessibility"), "accessibility"),
                parking=parking, infrastructure=score(get(row, "infrastructure"), "infrastructure"),
                target_match=score(get(row, "target_match"), "target_match"),
                space_sqm=num(get(row, "space_sqm") or get(row, "space") or get(row, "area_sqm"), "space_sqm")
            ))
        if len(locations) < 2:
            raise ValueError("CSV must contain at least two candidate locations.")
        if len({(x.name.lower(), x.area.lower()) for x in locations}) != len(locations):
            raise ValueError("CSV contains duplicate candidate locations.")
        return {"locations": [x.model_dump() for x in locations], "count": len(locations)}
    except (UnicodeDecodeError, csv.Error, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not process CSV: {exc}") from exc

@app.post("/api/location/export")
def export_results(payload: LocationAnalysisRequest):
    try:
        result = analyze(payload.profile, payload.locations, payload.weights)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["rank", "location", "area", "city", "score", "classification", "data_completeness", "space_sqm", "monthly_cost", "strengths", "weaknesses", "warnings"])
    for r in result.recommendations:
        writer.writerow([r.rank, r.name, r.area, r.city, r.score, r.classification, r.data_completeness,
                         r.space_sqm if r.space_sqm is not None else "", r.cost_total if r.cost_total is not None else "",
                         " | ".join(r.strengths), " | ".join(r.weaknesses), " | ".join(r.warnings)])
    stream.seek(0)
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="intelliops-location-recommendations.csv"'})
