
from uuid import uuid4
from typing import Any
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from modules.inventory_optimization.service import optimize_inventory

app = FastAPI(
    title="IntelliOps API",
    description="Inventory optimization and demand forecasting",
    version="1.0.0"
)

class PredictionRequest(BaseModel):
    use_case: str = "inventory_optimization"
    request_id: str | None = None
    input: dict[str, Any]
    options: dict[str, Any] | None = None

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/v1/predict/{use_case}")
def predict(use_case: str, request: PredictionRequest):
    request_id = request.request_id or str(uuid4())

    if use_case != "inventory_optimization":
        return JSONResponse(status_code=400, content={
            "success": False,
            "use_case": use_case,
            "request_id": request_id,
            "prediction": None,
            "explanation": None,
            "model": None,
            "errors": [{
                "code": "UNSUPPORTED_USE_CASE",
                "field": "use_case",
                "message": "This use case is not supported."
            }]
        })

    try:
        result = optimize_inventory(
            product_id=request.input["product_id"],
            current_stock=float(request.input["current_stock"]),
            lead_time_days=int(request.input["lead_time_days"]),
            review_period_days=int(request.input.get("review_period_days", 7)),
            safety_stock_days=int(request.input.get("safety_stock_days", 3))
        )

        return {
            "success": True,
            "use_case": use_case,
            "request_id": request_id,
            "prediction": result,
            "explanation": {
                "summary": "Inventory recommendation based on forecast demand and supplied inventory parameters.",
                "method": "Random Forest forecast with a 7-day-average fallback when the model predicts zero."
            },
            "model": {
                "name": "RandomForestRegressor",
                "status": "trained"
            },
            "errors": []
        }

    except (KeyError, TypeError, ValueError) as exc:
        return JSONResponse(status_code=400, content={
            "success": False,
            "use_case": use_case,
            "request_id": request_id,
            "prediction": None,
            "explanation": None,
            "model": None,
            "errors": [{
                "code": "INVALID_INPUT",
                "field": "input",
                "message": str(exc)
            }]
        })

    except FileNotFoundError as exc:
        return JSONResponse(status_code=503, content={
            "success": False,
            "use_case": use_case,
            "request_id": request_id,
            "prediction": None,
            "explanation": None,
            "model": None,
            "errors": [{
                "code": "MODEL_OR_DATA_UNAVAILABLE",
                "field": None,
                "message": str(exc)
            }]
        })
