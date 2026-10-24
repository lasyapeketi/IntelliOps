
from modules.complaint_sentiment.predict import (
    predict_complaint,
    analyze_sentiment,
)


def analyze_complaint(complaint_text: str) -> dict:
    if not isinstance(complaint_text, str) or not complaint_text.strip():
        raise ValueError("complaint_text must not be empty.")

    result = predict_complaint(complaint_text)

    return {
        "complaint_text": complaint_text.strip(),
        "complaint_category": result["complaint_category"],
        "category_confidence": result["confidence"],
        "sentiment": result["sentiment"],
        "sentiment_score": result["sentiment_score"],
    }

