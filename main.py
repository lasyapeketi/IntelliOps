import io
import json
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import MODEL_PATH, METRICS_PATH, RISK_THRESHOLD

app = FastAPI(title="Employee Attrition Prediction API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_model():
    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Model not trained. Download the dataset and run `python train_model.py` in the backend folder."
        )
    return joblib.load(MODEL_PATH)

def risk_label(probability: float) -> str:
    if probability >= 0.65:
        return "High"
    if probability >= RISK_THRESHOLD:
        return "Medium"
    return "Low"

def predict_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    bundle = get_model()
    pipeline = bundle["pipeline"]
    feature_columns = bundle["feature_columns"]
    # If an original dataset is uploaded, ignore the historical target column.
    frame = frame.drop(columns=["Attrition"], errors="ignore")
    missing = [col for col in feature_columns if col not in frame.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {', '.join(missing[:15])}"
        )
    X = frame[feature_columns].copy()
    probabilities = pipeline.predict_proba(X)[:, 1]
    results = []
    for index, probability in enumerate(probabilities):
        p = float(probability)
        results.append({
            "row": index + 1,
            "risk_score": round(p * 100, 1),
            "risk_level": risk_label(p),
            "predicted_attrition": bool(p >= RISK_THRESHOLD),
        })
    return results

class EmployeeInput(BaseModel):
    # Values are examples; use actual category values present in the training dataset.
    BusinessTravel: str = "Travel_Rarely"
    DailyRate: float = Field(default=800, ge=0)
    Department: str = "Research & Development"
    DistanceFromHome: float = Field(default=5, ge=0)
    Education: int = Field(default=3, ge=1, le=5)
    EducationField: str = "Life Sciences"
    EnvironmentSatisfaction: int = Field(default=3, ge=1, le=4)
    HourlyRate: float = Field(default=65, ge=0)
    JobInvolvement: int = Field(default=3, ge=1, le=4)
    JobLevel: int = Field(default=2, ge=1, le=5)
    JobRole: str = "Research Scientist"
    JobSatisfaction: int = Field(default=3, ge=1, le=4)
    MonthlyIncome: float = Field(default=5000, ge=0)
    MonthlyRate: float = Field(default=15000, ge=0)
    NumCompaniesWorked: float = Field(default=2, ge=0)
    OverTime: str = "No"
    PercentSalaryHike: float = Field(default=15, ge=0)
    PerformanceRating: int = Field(default=3, ge=1, le=4)
    RelationshipSatisfaction: int = Field(default=3, ge=1, le=4)
    StockOptionLevel: int = Field(default=1, ge=0, le=3)
    TotalWorkingYears: float = Field(default=8, ge=0)
    TrainingTimesLastYear: float = Field(default=3, ge=0)
    WorkLifeBalance: int = Field(default=3, ge=1, le=4)
    YearsAtCompany: float = Field(default=5, ge=0)
    YearsInCurrentRole: float = Field(default=3, ge=0)
    YearsSinceLastPromotion: float = Field(default=1, ge=0)
    YearsWithCurrManager: float = Field(default=3, ge=0)

@app.get("/api/health")
def health():
    return {"status": "ok", "model_ready": MODEL_PATH.exists()}

@app.get("/api/summary")
def summary():
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=503, detail="Train the model first.")
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))

@app.get("/api/features")
def features():
    if not MODEL_PATH.exists():
        raise HTTPException(status_code=503, detail="Train the model first.")
    bundle = get_model()
    return {"feature_columns": bundle["feature_columns"], "threshold": RISK_THRESHOLD}

@app.post("/api/predict")
def predict_one(employee: EmployeeInput):
    bundle = get_model()
    features = bundle["feature_columns"]
    data = employee.model_dump()
    # The form contains fields in the model's expected feature set for the standard dataset.
    missing = [col for col in features if col not in data]
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Single prediction form does not cover every model column. Use batch CSV upload for full dataset rows. Missing: " + ", ".join(missing[:10])
        )
    frame = pd.DataFrame([{col: data[col] for col in features}])
    result = predict_frame(frame)[0]
    result.pop("row", None)
    result["interpretation"] = "This is a model estimate, not a statement of employee intent."
    return result

@app.post("/api/predict-batch")
async def predict_batch(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV must be 10 MB or smaller.")
    try:
        frame = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}") from exc
    if frame.empty:
        raise HTTPException(status_code=400, detail="CSV contains no rows.")
    if len(frame) > 10000:
        raise HTTPException(status_code=400, detail="Maximum 10,000 rows per upload.")
    results = predict_frame(frame)
    output = frame.drop(columns=["Attrition"], errors="ignore").copy()
    output.insert(0, "PredictionRow", [r["row"] for r in results])
    output["AttritionRiskScore"] = [r["risk_score"] for r in results]
    output["RiskLevel"] = [r["risk_level"] for r in results]
    output["PredictedAttrition"] = ["Yes" if r["predicted_attrition"] else "No" for r in results]
    return {
        "count": len(results),
        "high_risk": sum(r["risk_level"] == "High" for r in results),
        "medium_risk": sum(r["risk_level"] == "Medium" for r in results),
        "low_risk": sum(r["risk_level"] == "Low" for r in results),
        "results": results,
        "csv": output.to_csv(index=False),
    }
