# modules/complaint_sentiment
# Customer Complaint & Sentiment Intelligence

## Overview

This module classifies customer complaints into predefined categories, estimates sentiment, and summarizes common complaint patterns to help businesses identify potential problem areas.

## Technology Stack

* Python
* Pandas
* Scikit-learn
* TF-IDF Vectorization
* Logistic Regression
* VADER Sentiment Analysis
* FastAPI
* Joblib

## Dataset

The module uses `data/complaints.csv`, containing 1,224 complaint records with two columns:

* `complaint_text`: Complaint description.
* `category`: Complaint category label.

The dataset is excluded from Git. Obtain the dataset separately before training the model.

## Model

TF-IDF converts complaint text into numerical features. Logistic Regression predicts one of six categories:

* Account Issue
* Billing Issue
* Delivery Issue
* Payment Issue
* Service Issue
* Technical Issue

The current random, stratified train/test split produced 98% accuracy. Because the dataset may contain similar or templated complaints, this result should be treated as preliminary rather than a guarantee of performance on unseen real-world complaints.

VADER provides rule-based sentiment estimates classified as Positive, Negative, or Neutral. These predictions have not been validated against human-labelled sentiment data.

## Running the Module

From the repository root:

Train the classifier:

```powershell
py -m modules.complaint_sentiment.model
```

Test predictions:

```powershell
py -m modules.complaint_sentiment.predict
```

Generate complaint insights:

```powershell
py -m modules.complaint_sentiment.insight
```

Run unit tests:

```powershell
py -m pytest modules/complaint_sentiment/tests/test_service.py -v
```

Start the current local API:

```powershell
py -m uvicorn main:app --reload
```

API documentation:
`http://127.0.0.1:8000/docs`

## API Contract

Endpoint: `POST /api/v1/predict/complaint_sentiment`

Request:

```json
{
  "use_case": "complaint_sentiment",
  "request_id": "req-001",
  "input": {
    "complaint_text": "My payment was deducted but the merchant did not receive it."
  },
  "options": {
    "include_explanation": false
  }
}
```

The response follows the shared IntelliOps envelope with `success`, `use_case`, `request_id`, `prediction`, `explanation`, `model`, and `errors`.

## Limitations

* The dataset is small and requires additional provenance documentation.
* The reported classification accuracy may be inflated by similar examples across the split.
* VADER sentiment is an unvalidated baseline for customer complaints.
* The API currently runs as a standalone local application and still needs integration with the shared backend.
* Complaint insights currently provide category and sentiment counts, not a fully validated business root-cause analysis.
