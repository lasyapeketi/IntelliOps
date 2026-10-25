# Customer Churn Prediction

## Overview

The `customer_churn` use case integrates the existing Customer Churn Prediction model into the IntelliOps FastAPI backend. It predicts whether a customer is likely to churn or stay using customer account and service information.

## Endpoint

`POST /api/v1/predict/customer_churn`

Health check: `GET /health`

## Request Format

The request follows the IntelliOps prediction API contract.

```json
{
  "use_case": "customer_churn",
  "request_id": "example-001",
  "input": {
    "SeniorCitizen": 0,
    "tenure": 12,
    "MonthlyCharges": 70.35,
    "gender": "Female",
    "Partner": "Yes",
    "Dependents": "No",
    "PhoneService": "Yes",
    "MultipleLines": "No",
    "InternetService": "DSL",
    "OnlineSecurity": "No",
    "OnlineBackup": "Yes",
    "DeviceProtection": "No",
    "TechSupport": "No",
    "StreamingTV": "No",
    "StreamingMovies": "Yes",
    "Contract": "Month-to-month",
    "PaperlessBilling": "Yes",
    "PaymentMethod": "Electronic check",
    "TotalCharges": 844.2
  },
  "options": {}
}
```

### Input fields

All 19 listed fields are required.

- Numeric fields: `SeniorCitizen`, `tenure`, `MonthlyCharges`, `TotalCharges`.
- Categorical fields: `gender`, `Partner`, `Dependents`, `PhoneService`, `MultipleLines`, `InternetService`, `OnlineSecurity`, `OnlineBackup`, `DeviceProtection`, `TechSupport`, `StreamingTV`, `StreamingMovies`, `Contract`, `PaperlessBilling`, `PaymentMethod`.

`SeniorCitizen` must be `0` or `1`. Tenure must be between `0` and `1000` months. Charges cannot be negative. Categorical fields must be non-empty strings.

## Successful Response

The response includes:

- `success`: whether the request succeeded.
- `use_case`: `customer_churn`.
- `request_id`: the supplied request ID, if any.
- `prediction.label`: `Churn` or `Stay`.
- `prediction.value`: `1` for churn and `0` for stay.
- `prediction.churn_probability`: predicted probability of churn.
- `prediction.confidence`: probability associated with the selected label.
- `model`: model name and version.
- `errors`: empty on success.

The current prediction threshold is `0.5`: probabilities at or above this threshold produce `Churn`.

## Error Handling

- `400`: invalid input or missing required feature fields.
- `404`: unknown use case.
- `500`: model unavailable or prediction failure.

Errors use the IntelliOps response envelope with an error code, field, and message.

## Model and Preprocessing

The API loads the existing `best_model.joblib` and `preprocessor.joblib` artifacts. It does not retrain the model for each request.

The model's reported prediction probability is based on its saved `predict_proba` output. Predictions should support customer-retention analysis and should not be treated as guarantees of future customer behavior.

## Run Locally

From the repository root, activate your virtual environment and run:

```powershell
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to inspect and try the API.

## Run Tests

```powershell
python -m pytest backend/customer_churn/tests/test_api.py -v
```

## Current Test Coverage

The automated API tests cover the health endpoint, successful prediction, missing feature validation, invalid numeric input, and unknown use cases.

## Model Limitations

Prediction quality depends on the existing training data, saved model, and preprocessing logic. Model accuracy and other evaluation metrics should be documented only after verifying the actual evaluation results.
