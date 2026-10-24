
from pathlib import Path

import pandas as pd

from modules.complaint_sentiment.predict import analyze_sentiment

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "complaints.csv"


def generate_complaint_insights() -> dict:
    if not DATA_PATH.exists():
        raise FileNotFoundError("Complaint dataset not found.")

    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["complaint_text", "category"]).copy()

    df["complaint_text"] = df["complaint_text"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip()

    df = df[
        (df["complaint_text"] != "") &
        (df["category"] != "")
    ]

    category_counts = df["category"].value_counts()

    sentiment_counts = {"Positive": 0, "Negative": 0, "Neutral": 0}

    for complaint in df["complaint_text"]:
        sentiment = analyze_sentiment(complaint)["sentiment"]
        sentiment_counts[sentiment] += 1

    total = len(df)

    return {
        "total_complaints_analyzed": total,
        "most_common_categories": [
            {
                "category": category,
                "count": int(count),
                "percentage": round(float(count / total * 100), 2),
            }
            for category, count in category_counts.head(5).items()
        ],
        "sentiment_distribution": sentiment_counts,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(generate_complaint_insights(), indent=2))
