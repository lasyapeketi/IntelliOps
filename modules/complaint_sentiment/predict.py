
from pathlib import Path
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import joblib

MODEL_PATH = Path(__file__).resolve().parent / "complaint_model.joblib"

_model = None

sentiment_analyzer = SentimentIntensityAnalyzer()


def analyze_sentiment(complaint_text: str) -> dict:
    scores = sentiment_analyzer.polarity_scores(complaint_text)
    compound = scores["compound"]

    if compound >= 0.05:
        sentiment = "Positive"
    elif compound <= -0.05:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    return {
        "sentiment": sentiment,
        "sentiment_score": round(compound, 4),
    }

def load_model():
    global _model

    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                "Trained model not found. Run model.py first."
            )

        _model = joblib.load(MODEL_PATH)

    return _model


def predict_complaint(complaint_text: str) -> dict:
    if not isinstance(complaint_text, str) or not complaint_text.strip():
        raise ValueError("Complaint text cannot be empty.")

    model = load_model()
    text = complaint_text.strip()

    category = model.predict([text])[0]
    probabilities = model.predict_proba([text])[0]

    sentiment_result = analyze_sentiment(text)

    return {
        "complaint_category": str(category),
        "confidence": round(float(max(probabilities)), 4),
        **sentiment_result,
    }


if __name__ == "__main__":
    samples = [
        "My payment was deducted but the merchant did not receive it.",
        "I received a damaged product and customer support is not responding.",
        "I cannot log in to my account.",
    ]

    for sample in samples:
        print(f"\nComplaint: {sample}")
        print(f"Prediction: {predict_complaint(sample)}")
