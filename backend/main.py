"""IntelliOps demand forecasting API endpoint."""

import logging
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from modules.demand_forecasting.train_model import (
    DATE_COLUMN,
    PRODUCT_COLUMN,
    TARGET_COLUMN,
    forecast_future_weeks,
    validate_weekly_dates,
)

USE_CASE = "demand_forecasting"
MODEL_PATH = ROOT_DIR / "demand_forecast_model.joblib"
DATA_PATH = ROOT_DIR / "ecommerce_demand_weekly.csv"

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

app = FastAPI(title="IntelliOps Demand Forecasting API")
_runtime: dict[str, Any] | None = None


class ForecastInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=64)
    horizon_weeks: int = Field(default=1, ge=1, le=52)


class PredictionOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_explanation: bool = False


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_case: str
    request_id: str | None = None
    input: ForecastInput
    options: PredictionOptions = Field(default_factory=PredictionOptions)


def response_body(
    *,
    success: bool,
    request_id: str | None,
    prediction: dict | None = None,
    explanation: dict | None = None,
    model: dict | None = None,
    errors: list[dict] | None = None,
) -> dict:
    return {
        "success": success,
        "use_case": USE_CASE,
        "request_id": request_id,
        "prediction": prediction,
        "explanation": explanation,
        "model": model,
        "errors": errors or [],
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str | None = None,
    field: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=response_body(
            success=False,
            request_id=request_id,
            errors=[{
                "code": code,
                "field": field,
                "message": message,
            }],
        ),
    )


def load_forecaster() -> dict[str, Any]:
    """Load and validate the model bundle and historical data."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError("The trained demand model is unavailable.")
    if not DATA_PATH.is_file():
        raise FileNotFoundError("The historical demand dataset is unavailable.")

    bundle = joblib.load(MODEL_PATH)
    if not isinstance(bundle, dict):
        raise ValueError("Invalid model bundle.")
    metadata = bundle.get("metadata")
    model = bundle.get("model")

    if not isinstance(metadata, dict) or not callable(
        getattr(model, "predict", None)
    ):
        raise ValueError("The model bundle is missing valid model metadata.")

    expected = {
        "date_column": DATE_COLUMN,
        "product_column": PRODUCT_COLUMN,
        "target_column": TARGET_COLUMN,
    }
    for key, expected_value in expected.items():
        if metadata.get(key) != expected_value:
            raise ValueError("The model metadata does not match the forecasting code.")

    history = pd.read_csv(
        DATA_PATH,
        usecols=[DATE_COLUMN, PRODUCT_COLUMN, TARGET_COLUMN],
    )
    history[DATE_COLUMN] = pd.to_datetime(history[DATE_COLUMN], errors="coerce")
    history[TARGET_COLUMN] = pd.to_numeric(
        history[TARGET_COLUMN], errors="coerce"
    )
    valid = (
        history[DATE_COLUMN].notna()
        & history[PRODUCT_COLUMN].notna()
        & history[TARGET_COLUMN].notna()
        & np.isfinite(history[TARGET_COLUMN])
        & (history[TARGET_COLUMN] >= 0)
    )
    history = history.loc[valid].copy()

    if history.empty:
        raise ValueError("No valid historical demand observations were found.")
    if history.duplicated([PRODUCT_COLUMN, DATE_COLUMN]).any():
        raise ValueError("Historical data has duplicate SKU-week observations.")

    validate_weekly_dates(history[DATE_COLUMN])
    history = history.sort_values(
        [PRODUCT_COLUMN, DATE_COLUMN], kind="stable"
    ).reset_index(drop=True)

    return {"bundle": bundle, "history": history, "metadata": metadata}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    body = exc.body if isinstance(exc.body, dict) else {}
    request_id = body.get("request_id")
    details = []
    for item in exc.errors():
        location = list(item.get("loc", ()))
        if location and location[0] == "body":
            location = location[1:]
        field = ".".join(str(part) for part in location) or None
        details.append({
            "code": "VALIDATION_ERROR",
            "field": field,
            "message": "A valid value is required.",
        })
    return JSONResponse(
        status_code=400,
        content=response_body(
            success=False,
            request_id=request_id,
            errors=details,
        ),
    )


@app.post("/api/v1/predict/demand_forecasting")
def predict_demand(payload: PredictionRequest, request: Request) -> JSONResponse:
    if payload.use_case != USE_CASE:
        return error_response(
            400, "INVALID_USE_CASE",
            f"use_case must be '{USE_CASE}'.",
            payload.request_id, "use_case",
        )

    global _runtime
    try:
        if _runtime is None:
            _runtime = load_forecaster()
        runtime = _runtime
    except Exception:
        LOGGER.exception("Demand forecasting could not load its model.")
        return error_response(
            503, "MODEL_UNAVAILABLE",
            "Demand forecasting is temporarily unavailable.",
            payload.request_id,
        )

    sku = payload.input.sku.strip()
    history = runtime["history"]
    sku_history = history.loc[history[PRODUCT_COLUMN] == sku].copy()

    if sku_history.empty:
        return error_response(
            400, "UNKNOWN_SKU",
            "No historical demand was found for the requested SKU.",
            payload.request_id, "input.sku",
        )

    origin = sku_history[DATE_COLUMN].max()
    try:
        forecasts = forecast_future_weeks(
            runtime["bundle"],
            sku_history[[DATE_COLUMN, PRODUCT_COLUMN, TARGET_COLUMN]],
            payload.input.horizon_weeks,
        )
        prediction = {
            "sku": sku,
            "forecast_origin": origin.date().isoformat(),
            "horizon_weeks": payload.input.horizon_weeks,
            "forecasts": [
                {
                    "forecast_date": row[DATE_COLUMN].date().isoformat(),
                    "predicted_demand": float(row["predicted_demand"]),
                }
                for _, row in forecasts.iterrows()
            ],
        }
    except Exception:
        LOGGER.exception("Forecast failed for the requested SKU.")
        return error_response(
            500, "PREDICTION_ERROR",
            "The forecasting model could not produce a prediction.",
            payload.request_id,
        )

    metadata = runtime["metadata"]
    explanation = None
    if payload.options.include_explanation:
        explanation = {
            "summary": (
                f"Forecasted weekly demand for SKU {sku} over "
                f"{payload.input.horizon_weeks} week(s)."
            ),
            "key_factors": [
                "Historical demand for the requested SKU",
                "Recursive weekly forecasts using prior predictions",
            ],
        }

    return JSONResponse(
        content=response_body(
            success=True,
            request_id=payload.request_id,
            prediction=prediction,
            explanation=explanation,
            model={
                "name": str(metadata.get("selected_model", "demand-forecast-model")),
                "version": str(metadata.get("model_version", "1.0")),
            },
        ),
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "use_case": USE_CASE,
        "model_artifact_present": MODEL_PATH.is_file(),
        "dataset_present": DATA_PATH.is_file(),
    }
