
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from modules.complaint_sentiment.service import analyze_complaint

app = FastAPI(
    title="IntelliOps API",
    description="Customer Complaint and Sentiment Intelligence",
    version="1.0.0",
)


class ComplaintFeatures(BaseModel):
    complaint_text: str = Field(
        ...,
        min_length=1,
        description="The customer's complaint text.",
    )


class PredictionOptions(BaseModel):
    include_explanation: bool = False


class PredictionRequest(BaseModel):
    use_case: str
    request_id: str | None = None
    input: ComplaintFeatures
    options: PredictionOptions = Field(default_factory=PredictionOptions)


def error_response(
    use_case: str,
    request_id: str | None,
    code: str,
    field: str | None,
    message: str,
    status_code: int,
):
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    body = exc.body if isinstance(exc.body, dict) else {}
    use_case = body.get("use_case", "complaint_sentiment")
    request_id = body.get("request_id")

    first_error = exc.errors()[0]
    location = first_error.get("loc", ())
    field = ".".join(str(part) for part in location if part != "body") or None

    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "use_case": use_case,
            "request_id": request_id,
            "prediction": None,
            "explanation": None,
            "model": None,
            "errors": [
                {
                    "code": "VALIDATION_ERROR",
                    "field": field,
                    "message": "A valid request body and complaint_text are required.",
                }
            ],
        },
    )


@app.get("/")
def home():
    return {"message": "IntelliOps API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/api/v1/predict/complaint_sentiment")
def predict_complaint(request: PredictionRequest):
    if request.use_case != "complaint_sentiment":
        return error_response(
            request.use_case,
            request.request_id,
            "VALIDATION_ERROR",
            "use_case",
            "use_case must be 'complaint_sentiment'.",
            400,
        )

    complaint_text = request.input.complaint_text.strip()

    if not complaint_text:
        return error_response(
            request.use_case,
            request.request_id,
            "VALIDATION_ERROR",
            "input.complaint_text",
            "Complaint text cannot be empty.",
            400,
        )

    try:
        result = analyze_complaint(complaint_text)
    except Exception:
        return error_response(
            request.use_case,
            request.request_id,
            "PREDICTION_ERROR",
            None,
            "The complaint could not be analyzed.",
            500,
        )

    explanation: dict[str, Any] | None = None

    if request.options.include_explanation:
        explanation = {
            "summary": (
                f"Complaint classified as {result['complaint_category']} "
                f"with {result['sentiment'].lower()} sentiment."
            ),
            "key_factors": [],
        }

    return {
        "success": True,
        "use_case": "complaint_sentiment",
        "request_id": request.request_id,
        "prediction": {
            "complaint_category": result["complaint_category"],
            "category_confidence": result["category_confidence"],
            "sentiment": result["sentiment"],
            "sentiment_score": result["sentiment_score"],
        },
        "explanation": explanation,
        "model": {
            "name": "TF-IDF + Logistic Regression with VADER sentiment",
            "version": "1.0",
        },
        "errors": [],
    }

