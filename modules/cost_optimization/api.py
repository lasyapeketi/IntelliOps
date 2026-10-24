
from math import isfinite
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.cost_optimization.service import analyze_costs


router = APIRouter()


class ResourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str
    total_cost: float
    used_capacity: float
    total_capacity: float

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("resource_id cannot be blank.")
        return value

    @field_validator("total_cost", "used_capacity", "total_capacity")
    @classmethod
    def validate_finite_numbers(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Value must be finite.")
        return value


class CostHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str
    total_cost: float

    @field_validator("period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("period cannot be blank.")
        return value

    @field_validator("total_cost")
    @classmethod
    def validate_cost(cls, value: float) -> float:
        if not isfinite(value) or value < 0:
            raise ValueError("total_cost must be finite and non-negative.")
        return value


class CostOptimizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resources: list[ResourceInput] = Field(min_length=1)
    utilization_threshold: float = Field(default=50.0, ge=0, le=100)
    cost_history: list[CostHistoryInput] = Field(default_factory=list)
    variance_threshold_percent: float = Field(default=20.0, ge=0, le=1000)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_case: str
    request_id: str | None = None
    input: CostOptimizationInput
    options: dict[str, Any] = Field(default_factory=dict)


def error_response(
    *,
    use_case: str,
    request_id: str | None,
    status_code: int,
    code: str,
    field: str | None,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "use_case": use_case,
            "request_id": request_id,
            "prediction": None,
            "explanation": None,
            "model": None,
            "errors": [
                {
                    "code": code,
                    "field": field,
                    "message": message,
                }
            ],
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register standard IntelliOps error responses."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = [
            {
                "code": "VALIDATION_ERROR",
                "field": (
                    ".".join(
                        str(part)
                        for part in error["loc"]
                        if part != "body"
                    )
                    or None
                ),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "use_case": "cost_optimization",
                "request_id": None,
                "prediction": None,
                "explanation": None,
                "model": None,
                "errors": errors,
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return error_response(
            use_case="cost_optimization",
            request_id=None,
            status_code=500,
            code="INTERNAL_ERROR",
            field=None,
            message="An unexpected error occurred.",
        )


@router.post("/api/v1/predict/cost_optimization")
def predict_cost_optimization(request: PredictionRequest):
    if request.use_case != "cost_optimization":
        return error_response(
            use_case=request.use_case,
            request_id=request.request_id,
            status_code=400,
            code="VALIDATION_ERROR",
            field="use_case",
            message="use_case must be cost_optimization.",
        )

    try:
        result = analyze_costs(
            resources=[
                resource.model_dump()
                for resource in request.input.resources
            ],
            utilization_threshold=request.input.utilization_threshold,
            cost_history=[
                item.model_dump()
                for item in request.input.cost_history
            ],
            variance_threshold_percent=(
                request.input.variance_threshold_percent
            ),
        )
    except ValueError as exc:
        return error_response(
            use_case=request.use_case,
            request_id=request.request_id,
            status_code=400,
            code="VALIDATION_ERROR",
            field="input",
            message=str(exc),
        )
    except Exception:
        return error_response(
            use_case=request.use_case,
            request_id=request.request_id,
            status_code=500,
            code="INTERNAL_ERROR",
            field=None,
            message="An unexpected error occurred.",
        )

    flagged_resources = [
        {
            "resource_id": resource["resource_id"],
            "flags": resource["flags"],
            "utilization_percent": resource["utilization_percent"],
        }
        for resource in result["resources"]
        if resource["flags"]
    ]

    flagged_periods = [
        period
        for period in result["cost_history_analysis"]["periods"]
        if period["flags"]
    ]

    return {
        "success": True,
        "use_case": "cost_optimization",
        "request_id": request.request_id,
        "prediction": result,
        "explanation": {
            "summary": (
                "Cost and resource analysis completed "
                "using rule-based calculations."
            ),
            "key_factors": flagged_resources,
            "cost_variance_flags": flagged_periods,
            "data_warnings": result["cost_history_analysis"]["warnings"],
        },
        "model": None,
        "errors": [],
    }
