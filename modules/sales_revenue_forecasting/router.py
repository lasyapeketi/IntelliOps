from typing import Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from modules.sales_revenue_forecasting.schemas import PredictionRequest
from modules.sales_revenue_forecasting.service import (
    USE_CASE_NAME,
    forecast_sales_revenue,
)

router = APIRouter(tags=["Sales & Revenue Forecasting"])


def build_error_response(
    request_id: str | None,
    message: str,
    status_code: int = 400,
    field: str | None = None,
    code: str = "VALIDATION_ERROR",
    use_case: str = USE_CASE_NAME,
) -> JSONResponse:
    """Build standardized IntelliOps error envelope."""
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


@router.post("/api/v1/predict/sales_revenue_forecasting")
def predict_sales_revenue(request: PredictionRequest) -> Any:
    """Predict future sales and revenue across a specified horizon."""
    # 1. Validate use_case identifier
    if request.use_case != USE_CASE_NAME:
        return build_error_response(
            request_id=request.request_id,
            message=f"use_case must be '{USE_CASE_NAME}'.",
            field="use_case",
            status_code=400,
            use_case=request.use_case,
        )

    # 2. Invoke Service Layer
    try:
        response_data = forecast_sales_revenue(
            historical_sales=request.input.historical_sales,
            forecast_horizon_months=request.input.forecast_horizon_months,
            marketing_budget=request.input.marketing_budget,
            seasonality_factor=request.input.seasonality_factor,
            discount_rate_pct=request.input.discount_rate_pct,
            include_explanation=request.options.include_explanation,
            request_id=request.request_id,
        )
        return response_data

    except ValueError as exc:
        return build_error_response(
            request_id=request.request_id,
            message=str(exc),
            field="input",
            status_code=400,
        )
    except Exception as exc:
        return build_error_response(
            request_id=request.request_id,
            message=f"An unexpected error occurred during forecasting: {str(exc)}",
            field=None,
            code="INTERNAL_SERVER_ERROR",
            status_code=500,
        )
