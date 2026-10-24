
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from modules.cost_optimization.service import analyze_costs


router = APIRouter()

class ResourceInput(BaseModel):
    resource_id: str
    total_cost: float
    used_capacity: float
    total_capacity: float
    
class CostOptimizationInput(BaseModel):
    resources: list[ResourceInput] = Field(min_length=1)
    utilization_threshold: float = Field(default=50.0, ge=0, le=100)

class PredictionRequest(BaseModel):
    use_case: str
    request_id: str | None = None
    input: CostOptimizationInput
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/v1/predict/cost_optimization")
def predict_cost_optimization(request: PredictionRequest) -> dict:
    if request.use_case != "cost_optimization":
        return {
            "success": False,
            "use_case": request.use_case,
            "request_id": request.request_id,
            "prediction": None,
            "explanation": None,
            "model": None,
            "errors": [
                {
                    "code": "VALIDATION_ERROR",
                    "field": "use_case",
                    "message": "use_case must be cost_optimization.",
                }
            ],
        }

    try:
        result = analyze_costs(
            resources=[
                resource.model_dump()
                for resource in request.input.resources
            ],
            utilization_threshold=request.input.utilization_threshold,
        )
    except ValueError as exc:
        return {
            "success": False,
            "use_case": request.use_case,
            "request_id": request.request_id,
            "prediction": None,
            "explanation": None,
            "model": None,
            "errors": [
                {
                    "code": "VALIDATION_ERROR",
                    "field": "input.resources",
                    "message": str(exc),
                }
            ],
        }

    return {
        "success": True,
        "use_case": request.use_case,
        "request_id": request.request_id,
        "prediction": result,
        "explanation": {
            "summary": "Cost and resource utilization analysis completed.",
            "key_factors": [
                {
                    "resource_id": resource["resource_id"],
                    "flags": resource["flags"],
                    "utilization_percent": resource["utilization_percent"],
                }
                for resource in result["resources"]
                if resource["flags"]
            ],
        },
        "model": None,
        "errors": [],
    }
