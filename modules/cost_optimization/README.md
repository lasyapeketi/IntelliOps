
# Cost & Resource Optimization

## Overview

This module analyzes resource costs and capacity utilization to identify resources that may need review.

It currently uses rule-based calculations. It does not use a trained machine-learning model.

## API Endpoint

`POST /api/v1/predict/cost_optimization`

The module exposes a FastAPI router. The shared application has not yet been implemented, so the router must be registered when the team integrates the backend.

## Request Format

```json
{
  "use_case": "cost_optimization",
  "request_id": "req-001",
  "input": {
    "resources": [
      {
        "resource_id": "WH-001",
        "total_cost": 200000,
        "used_capacity": 45,
        "total_capacity": 100
      }
    ],
    "utilization_threshold": 50
  },
  "options": {}
}
```

`request_id` and `options` are optional. The utilization threshold defaults to 50%.

Each resource requires:
- `resource_id`: unique resource identifier
- `total_cost`: non-negative cost
- `used_capacity`: used capacity, from zero to total capacity
- `total_capacity`: positive total capacity

## Analysis Output

A successful response includes:
- Resource count
- Total and average cost
- Utilization threshold
- Per-resource utilization percentage
- Review flags for resources below the threshold
- Notes describing the analysis limitations

Low utilization is a review flag, not proof of waste.

## Validation

The service rejects:
- Empty resource lists
- Missing or blank resource IDs
- Duplicate resource IDs
- Negative costs
- Non-positive total capacity
- Used capacity outside the valid range
- Utilization thresholds outside 0–100

## Testing

Run the tests from the repository root:

`python -m pytest tests -v`

The module has unit tests for the analysis service and API tests for successful and invalid requests.

## Current Limitations

- No trained ML model is used.
- No future cost prediction or anomaly detection is implemented.
- No database integration or frontend integration is included.
- The router requires registration in the shared FastAPI application.
