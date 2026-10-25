
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .business_risk import (
    RISK_MODEL_NAME,
    RISK_MODEL_VERSION,
    analyze_business_risk,
)

app = FastAPI(
    title="IntelliOps - Business Risk & Event Intelligence",
    version="0.1.0",
)


class FinancialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revenue_change_pct: float = Field(default=0, ge=-100, le=1000)
    cost_change_pct: float = Field(default=0, ge=-100, le=1000)
    cash_runway_months: float = Field(default=12, ge=0, le=1200)


class OperationalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_disruption: bool = False
    delivery_delay_rate_pct: float = Field(default=0, ge=0, le=100)
    downtime_hours: float = Field(default=0, ge=0, le=8760)


class ExternalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    severity: Literal["low", "medium", "high", "critical"]


class BusinessRiskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial: FinancialInput = Field(default_factory=FinancialInput)
    operational: OperationalInput = Field(default_factory=OperationalInput)
    external_events: list[ExternalEvent] = Field(
        default_factory=list, max_length=100
    )


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_case: Literal["business_risk"]
    request_id: str | None = Field(default=None, max_length=100)
    input: BusinessRiskInput
    options: dict[str, Any] = Field(default_factory=dict)


def error_envelope(
    use_case: str,
    request_id: str | None,
    code: str,
    field: str | None,
    message: str,
) -> dict[str, Any]:
    return {
        "success": False,
        "use_case": use_case,
        "request_id": request_id,
        "prediction": None,
        "explanation": None,
        "model": None,
        "errors": [
            {"code": code, "field": field, "message": message}
        ],
    }


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
):
    body = exc.body if isinstance(exc.body, dict) else {}

    errors = []
    for error in exc.errors():
        location = ".".join(
            str(part) for part in error["loc"] if part != "body"
        )
        errors.append({
            "code": "VALIDATION_ERROR",
            "field": location or None,
            "message": error["msg"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "use_case": body.get("use_case", "business_risk"),
            "request_id": body.get("request_id"),
            "prediction": None,
            "explanation": None,
            "model": None,
            "errors": errors,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "business-risk"}


@app.post("/api/v1/predict/{use_case}")
def predict(use_case: str, request: PredictionRequest):
    if use_case != "business_risk" or request.use_case != use_case:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                "business_risk",
                request.request_id,
                "INVALID_USE_CASE",
                "use_case",
                "The path and body must use 'business_risk'.",
            ),
        )

    result = analyze_business_risk(request.input.model_dump())

    include_explanation = request.options.get(
        "include_explanation", True
    )

    prediction = {
        "label": result["label"],
        "value": result["value"],
        "confidence": result["confidence"],
        "risk_level": result["risk_level"],
    }

    explanation = None
    if include_explanation:
        explanation = {
            "summary": (
                f"Business risk assessed as {result['risk_level']} "
                f"with a rule-based score of {result['value']}/100."
            ),
            "key_factors": result["risk_factors"],
            "recommended_action": result["recommended_action"],
            "assessment_type": result["assessment_type"],
        }

    return {
        "success": True,
        "use_case": "business_risk",
        "request_id": request.request_id,
        "prediction": prediction,
        "explanation": explanation,
        "model": {
            "name": RISK_MODEL_NAME,
            "version": RISK_MODEL_VERSION,
        },
        "errors": [],
    }
