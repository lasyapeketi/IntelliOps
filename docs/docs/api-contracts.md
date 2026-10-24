# IntelliOps — API Contracts

## 1. Purpose

This document defines the standard API request and response formats for all 11 IntelliOps use cases. Every member must follow these contracts when implementing and integrating their module.

## 2. API Standards

- Backend framework: FastAPI.
- Communication: REST over HTTP.
- Request and response body format: JSON.
- Content type: `application/json`.
- JSON field naming: `snake_case`.
- Each use case must have a clearly defined endpoint.
- Inputs must be validated before prediction.
- All responses must follow the standard response structure defined below.

## 3. Standard Prediction Request

Every prediction endpoint must accept this common request structure.

```json
{
  "use_case": "delivery_delay",
  "request_id": "req-001",
  "input": {
    "feature_1": "value",
    "feature_2": 0,
    "feature_3": true
  },
  "options": {
    "include_explanation": false
  }
}
```

### Request field rules

- `use_case`: Required string identifying the selected module.
- `request_id`: Optional string used to trace a request. If supplied, return the same value in the response.
- `input`: Required object containing the features needed by the selected use case.
- `options`: Optional object containing supported configuration options.

The feature names and data types inside `input` must be documented separately for each use case. The example features above are placeholders, not actual model requirements.

## 4. Standard Successful Response

All successful predictions must use this common response envelope.

```json
{
  "success": true,
  "use_case": "delivery_delay",
  "request_id": "req-001",
  "prediction": {
    "label": "delayed",
    "value": 1,
    "confidence": 0.87
  },
  "explanation": {
    "summary": "The shipment is predicted to be delayed.",
    "key_factors": []
  },
  "model": {
    "name": "delivery-delay-model",
    "version": "1.0"
  },
  "errors": []
}
```

### Response field rules

- `success`: Boolean indicating whether the request succeeded.
- `use_case`: Identifier of the module that processed the request.
- `request_id`: The supplied request ID, or `null` if not supplied.
- `prediction`: Object containing the use-case-specific prediction.
- `explanation`: Object containing optional explanatory details, or `null` if unavailable.
- `model`: Object containing model metadata, or `null` when no model metadata applies.
- `errors`: Empty array when the request succeeds.

The fields inside `prediction` may differ by use case, but the common top-level keys must remain unchanged.

## 5. Standard Error Response

All validation failures and application errors must follow this structure.

```json
{
  "success": false,
  "use_case": "delivery_delay",
  "request_id": "req-001",
  "prediction": null,
  "explanation": null,
  "model": null,
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "field": "input.feature_1",
      "message": "A valid value is required."
    }
  ]
}
```

### Error field rules

- `code`: Machine-readable error identifier.
- `field`: Field associated with the error, or `null` if not applicable.
- `message`: Clear explanation of the problem.
- `errors`: One or more structured error objects.

Use appropriate HTTP status codes, such as `400` for invalid requests, `404` for unknown endpoints, and `500` for unexpected server errors. Do not expose stack traces, secrets, or internal paths.

## 6. Use-Case Identifiers

Use these exact identifiers in API requests and responses.

| No. | Use Case | Identifier |
|---|---|---|
| 1 | Cost & Resource Optimization | `cost_optimization` |
| 2 | Delivery Delay Prediction | `delivery_delay` |
| 3 | Demand Forecasting | `demand_forecasting` |
| 4 | Inventory Optimization & Replenishment | `inventory_optimization` |
| 5 | Business Risk & Event Intelligence | `business_risk` |
| 6 | Customer Behavior & Churn Prediction | `customer_churn` |
| 7 | Resource Allocation & Workforce Optimization | `workforce_optimization` |
| 8 | Customer Complaint & Sentiment Intelligence | `complaint_sentiment` |
| 9 | Employee Attrition Prediction | `employee_attrition` |
| 10 | Business Location Recommendation | `location_recommendation` |
| 11 | Sales & Revenue Forecasting | `sales_revenue_forecasting` |

## 7. Endpoint Naming

Use this endpoint naming convention:

`POST /api/v1/predict/{use_case}`

Examples:

- `POST /api/v1/predict/cost_optimization`
- `POST /api/v1/predict/delivery_delay`
- `POST /api/v1/predict/demand_forecasting`

Each endpoint must validate its own required input fields. The backend may use a shared prediction endpoint or separate routers, provided the agreed request and response contracts are preserved.

## 8. Integration Rules

1. Keep all common top-level response keys consistent.
2. Use the exact use-case identifiers listed in this document.
3. Do not rename JSON fields without updating the shared contract and coordinating the change.
4. Keep FastAPI schemas, frontend TypeScript types, tests, and documentation consistent.
5. Do not return hardcoded predictions as if they came from a trained model.
6. Document each use case's specific inputs, prediction outputs, and evaluation metrics.
7. Test success responses, invalid inputs, and unexpected errors before submitting a pull request.

## 9. Contract Status

These contracts are the shared integration standard for IntelliOps. Use-case-specific input and prediction fields must be documented by the assigned member before frontend integration. Any change to the common envelope must be coordinated and reflected in this file.
