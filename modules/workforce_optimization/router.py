
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from modules.workforce_optimization.service import optimize_workforce


router = APIRouter(tags=["Workforce Optimization"])

USE_CASE = "workforce_optimization"


class WorkforceInput(BaseModel):
    task: dict[str, Any]
    employees: list[dict[str, Any]] = Field(min_length=1)


class PredictionRequest(BaseModel):
    use_case: str
    request_id: str | None = None
    input: WorkforceInput
    options: dict[str, Any] = Field(default_factory=dict)


def error_response(
    request_id: str | None,
    message: str,
    status_code: int = 400,
    field: str | None = None,
    code: str = "VALIDATION_ERROR",
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "use_case": USE_CASE,
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


@router.post("/api/v1/predict/workforce_optimization")
def predict_workforce(request: PredictionRequest):
    if request.use_case != USE_CASE:
        return error_response(
            request_id=request.request_id,
            message=f"use_case must be '{USE_CASE}'.",
            field="use_case",
        )

    try:
        result = optimize_workforce(
            task=request.input.task,
            employees=request.input.employees,
            request_id=request.request_id,
        )
        return result

    except ValueError as exc:
        return error_response(
            request_id=request.request_id,
            message=str(exc),
            field="input",
        )


