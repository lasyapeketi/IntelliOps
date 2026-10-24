from pathlib import Path

import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "complaints.csv"
MODEL_PATH = Path(__file__).resolve().parent / "complaint_model.joblib"


def train_model():
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}\n"
            "Add a labeled complaints.csv file to the data folder."
        )

    df = pd.read_csv(DATA_PATH)

    required_columns = {"complaint_text", "category"}
    if not required_columns.issubset(df.columns):
        raise ValueError(
            f"Dataset must contain these columns: {required_columns}"
        )

    df = df.dropna(subset=["complaint_text", "category"])
    df["complaint_text"] = df["complaint_text"].astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip()
    df = df[
        (df["complaint_text"] != "")
        & (df["category"] != "")
    ]

    if df["category"].nunique() < 2:
        raise ValueError("At least two complaint categories are required.")

    if df["category"].value_counts().min() < 2:
        raise ValueError(
            "Each category needs at least two examples for stratified splitting."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        df["complaint_text"],
        df["category"],
        test_size=0.2,
        random_state=42,
        stratify=df["category"],
    )

    model = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                max_features=20000,
            ),
        ),
        (
            "classifier",
            LogisticRegression(max_iter=1000),
        ),
    ])

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    print("Complaint classification evaluation:")
    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0,
        )
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    train_model()


