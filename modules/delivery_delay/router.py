"""FastAPI Router for Delivery Delay Prediction.

Exposes REST prediction endpoints adhering strictly to the IntelliOps shared API envelope.
Routes provided:
- POST /api/v1/predict/delivery_delay (official docs/api-contracts.md route)
- POST /api/v1/delivery-delay/predict (guidelines alias)
"""

from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from modules.delivery_delay.service import (
    DeliveryDelayService,
    DeliveryDelayValidationError,
)

router = APIRouter(tags=["Delivery Delay Prediction"])
service = DeliveryDelayService()


# ---------------------------------------------------------------------------
# Pydantic Schemas for OpenAPI Documentation
# ---------------------------------------------------------------------------

class DeliveryDelayInput(BaseModel):
    """Input features required for delivery delay inference."""

    distance_km: float = Field(
        ...,
        gt=0.0,
        description="Distance between origin and destination in kilometers (> 0).",
        examples=[420.5],
    )
    shipping_method: Literal["standard", "express", "same_day", "overnight"] = Field(
        ...,
        description="Logistics service tier.",
        examples=["standard"],
    )
    promised_delivery_days: int = Field(
        ...,
        ge=1,
        description="Delivery commitment window in days (>= 1).",
        examples=[3],
    )
    historical_avg_delivery_days: float = Field(
        ...,
        gt=0.0,
        description="Carrier's historical average transit duration on this route in days (> 0).",
        examples=[3.8],
    )
    order_volume: int = Field(
        ...,
        ge=1,
        description="Consignment volume or item package count (>= 1).",
        examples=[4],
    )


class DeliveryDelayOptions(BaseModel):
    """Optional configuration for the prediction request."""

    include_explanation: bool = Field(
        default=True,
        description="Whether to include dynamic summary and explanatory key factors.",
    )


class DeliveryDelayRequest(BaseModel):
    """Standard IntelliOps prediction request envelope."""

    use_case: str = Field(
        default="delivery_delay",
        description="Target use case identifier.",
        examples=["delivery_delay"],
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Optional client-generated tracking identifier.",
        examples=["req-deliv-001"],
    )
    input: DeliveryDelayInput
    options: Optional[DeliveryDelayOptions] = Field(default_factory=DeliveryDelayOptions)


class PredictionResult(BaseModel):
    label: str = Field(..., description="'delayed' or 'on_time'")
    value: int = Field(..., description="1 for delayed, 0 for on_time")
    confidence: float = Field(..., description="Calibrated class probability [0.0, 1.0]")


class ExplanationResult(BaseModel):
    summary: str = Field(..., description="Human-readable decision explanation")
    key_factors: List[str] = Field(..., description="Top contributing operational drivers")


class ModelMetadata(BaseModel):
    name: str = Field(default="delivery-delay-model")
    version: str = Field(default="1.0")


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Standardized error code")
    field: Optional[str] = Field(None, description="Field associated with the validation error")
    message: str = Field(..., description="Error description")


class DeliveryDelaySuccessResponse(BaseModel):
    """Standard successful prediction response envelope."""

    success: bool = True
    use_case: str = "delivery_delay"
    request_id: Optional[str] = None
    prediction: PredictionResult
    explanation: Optional[ExplanationResult] = None
    model: ModelMetadata
    errors: List[ErrorDetail] = Field(default_factory=list)


class DeliveryDelayErrorResponse(BaseModel):
    """Standard error response envelope."""

    success: bool = False
    use_case: str = "delivery_delay"
    request_id: Optional[str] = None
    prediction: Optional[PredictionResult] = None
    explanation: Optional[ExplanationResult] = None
    model: Optional[ModelMetadata] = None
    errors: List[ErrorDetail]


# ---------------------------------------------------------------------------
# Endpoint Handlers
# ---------------------------------------------------------------------------

async def handle_delivery_delay_prediction(request: Request) -> JSONResponse:
    """Core request handler enforcing contract envelope and structured error responses."""
    request_id: Optional[str] = None
    use_case: str = "delivery_delay"

    try:
        raw_body: Any = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "use_case": use_case,
                "request_id": None,
                "prediction": None,
                "explanation": None,
                "model": None,
                "errors": [
                    {
                        "code": "INVALID_JSON",
                        "field": None,
                        "message": "Malformed JSON payload in request body.",
                    }
                ],
            },
        )

    if isinstance(raw_body, dict):
        request_id = raw_body.get("request_id")

    # Delegate processing and validation to service layer
    result = service.process_request(raw_body)

    if result.get("success"):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result,
        )
    else:
        # Check error code to choose suitable HTTP status
        errors = result.get("errors", [])
        status_code = 422
        if any(err.get("code") == "INTERNAL_SERVER_ERROR" for err in errors):
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        return JSONResponse(
            status_code=status_code,
            content=result,
        )


@router.post(
    "/predict/delivery_delay",
    response_model=DeliveryDelaySuccessResponse,
    responses={
        400: {"model": DeliveryDelayErrorResponse},
        422: {"model": DeliveryDelayErrorResponse},
        500: {"model": DeliveryDelayErrorResponse},
    },
    summary="Predict delivery delay (docs/api-contracts.md official route)",
)
async def predict_official(request: Request):
    return await handle_delivery_delay_prediction(request)


@router.post(
    "/delivery-delay/predict",
    response_model=DeliveryDelaySuccessResponse,
    responses={
        400: {"model": DeliveryDelayErrorResponse},
        422: {"model": DeliveryDelayErrorResponse},
        500: {"model": DeliveryDelayErrorResponse},
    },
    summary="Predict delivery delay (guidelines alias route)",
)
async def predict_alias(request: Request):
    return await handle_delivery_delay_prediction(request)
