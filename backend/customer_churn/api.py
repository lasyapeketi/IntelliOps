
from pathlib import Path
from typing import Any
import math

import joblib
import pandas as pd
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "best_model.joblib"
PREPROCESSOR_PATH = BASE_DIR / "models" / "preprocessor.joblib"

USE_CASE = "customer_churn"
MODEL_VERSION = "1.0"

REQUIRED_FEATURES = [
    "SeniorCitizen",
    "tenure",
    "MonthlyCharges",
    "gender",
    "Partner",
    "Dependents",
    "PhoneService",
    "MultipleLines",
    "InternetService",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
    "TotalCharges",
]

NUMERIC_FEATURES = {
    "SeniorCitizen",
    "tenure",
    "MonthlyCharges",
    "TotalCharges",
}

CATEGORICAL_FEATURES = [
    "gender",
    "Partner",
    "Dependents",
    "PhoneService",
    "MultipleLines",
    "InternetService",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
]


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_case: str
    request_id: str | None = None
    input: dict[str, Any]
    options: dict[str, Any] = Field(default_factory=dict)


def error_response(
    request_id: str | None,
    code: str,
    field: str | None,
    message: str,
) -> dict:
    return {
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
    }


def error_result(
    status_code: int,
    request_id: str | None,
    code: str,
    field: str | None,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(request_id, code, field, message),
    )


@router.post("/api/v1/predict/{use_case}")
def predict(use_case: str, request: PredictionRequest):
    request_id = request.request_id

    if use_case != USE_CASE or request.use_case != USE_CASE:
        return error_result(
            404,
            request_id,
            "UNKNOWN_USE_CASE",
            "use_case",
            "The requested use case is not supported.",
        )

    missing = [
        feature
        for feature in REQUIRED_FEATURES
        if feature not in request.input
    ]

    if missing:
        return error_result(
            400,
            request_id,
            "VALIDATION_ERROR",
            "input",
            f"Missing required fields: {', '.join(missing)}",
        )

    customer = dict(request.input)

    for name in NUMERIC_FEATURES:
        value = customer[name]

        if isinstance(value, bool) or value is None:
            return error_result(
                400,
                request_id,
                "VALIDATION_ERROR",
                f"input.{name}",
                "A numeric value is required.",
            )

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return error_result(
                400,
                request_id,
                "VALIDATION_ERROR",
                f"input.{name}",
                "A valid numeric value is required.",
            )

        if not math.isfinite(numeric_value):
            return error_result(
                400,
                request_id,
                "VALIDATION_ERROR",
                f"input.{name}",
                "The value must be finite.",
            )

        customer[name] = numeric_value

    if customer["SeniorCitizen"] not in (0, 1):
        return error_result(
            400,
            request_id,
            "VALIDATION_ERROR",
            "input.SeniorCitizen",
            "SeniorCitizen must be 0 or 1.",
        )

    if not 0 <= customer["tenure"] <= 1000:
        return error_result(
            400,
            request_id,
            "VALIDATION_ERROR",
            "input.tenure",
            "Tenure must be between 0 and 1000 months.",
        )

    for name in ("MonthlyCharges", "TotalCharges"):
        if customer[name] < 0:
            return error_result(
                400,
                request_id,
                "VALIDATION_ERROR",
                f"input.{name}",
                "Charges cannot be negative.",
            )

    for name in CATEGORICAL_FEATURES:
        value = customer[name]

        if not isinstance(value, str) or not value.strip():
            return error_result(
                400,
                request_id,
                "VALIDATION_ERROR",
                f"input.{name}",
                "A non-empty string value is required.",
            )

        customer[name] = value.strip()

    if not MODEL_PATH.is_file() or not PREPROCESSOR_PATH.is_file():
        return error_result(
            500,
            request_id,
            "MODEL_UNAVAILABLE",
            None,
            "The prediction model is not available.",
        )

    try:
        from backend.customer_churn.preprocess import ChurnPreprocessor

        model = joblib.load(MODEL_PATH)
        preprocessor = ChurnPreprocessor.load(str(PREPROCESSOR_PATH))

        customer_frame = pd.DataFrame(
            [{name: customer[name] for name in REQUIRED_FEATURES}]
        )

        transformed = preprocessor.transform(customer_frame)

        probabilities = model.predict_proba(transformed)[0]
        classes = list(model.classes_)

        if 1 not in classes:
            return error_result(
                500,
                request_id,
                "MODEL_CONFIGURATION_ERROR",
                None,
                "The model does not contain the expected churn class.",
            )

        churn_index = classes.index(1)
        churn_probability = float(probabilities[churn_index])

        label = "Churn" if churn_probability >= 0.5 else "Stay"
        confidence = (
            churn_probability
            if label == "Churn"
            else 1.0 - churn_probability
        )

        return {
            "success": True,
            "use_case": USE_CASE,
            "request_id": request_id,
            "prediction": {
                "label": label,
                "value": int(label == "Churn"),
                "churn_probability": round(churn_probability, 4),
                "confidence": round(confidence, 4),
            },
            "explanation": None,
            "model": {
                "name": type(model).__name__,
                "version": MODEL_VERSION,
            },
            "errors": [],
        }

    except Exception:
        return error_result(
            500,
            request_id,
            "PREDICTION_ERROR",
            None,
            "The prediction could not be completed.",
        )
