
# Cost & Resource Optimization

## Overview

This module analyzes resource costs, utilization, historical spending changes,
and potential opportunities for review.

It currently uses deterministic, rule-based calculations. It does not use a
trained machine-learning model, and no real business dataset is included.

## API Endpoint

`POST /api/v1/predict/cost_optimization`

The module exposes a FastAPI router. Register it with the shared FastAPI
application during backend integration.

## Request Format

```json
{
  "use_case": "cost_optimization",
  "request_id": "req-001",
  "input": {
    "resources": [
      {
        "resource_id": "R1",
        "total_cost": 1000,
        "used_capacity": 40,
        "total_capacity": 100
      }
    ],
    "utilization_threshold": 50,
    "cost_history": [
      {"period": "2026-01", "total_cost": 1000},
      {"period": "2026-02", "total_cost": 1400}
    ],
    "variance_threshold_percent": 20
  },
  "options": {}
}
```

`request_id` and `options` are optional. Utilization defaults to 50%.
The variance threshold defaults to 20%.

Historical periods must be supplied in chronological order. Each period
requires a unique label and a non-negative total cost.

## Outputs

A successful response contains the shared IntelliOps response envelope:
`success`, `use_case`, `request_id`, `prediction`, `explanation`, `model`,
and `errors`.

The prediction includes:

- Resource count, total cost, and average cost.
- Utilization and unused-capacity percentages.
- Low-utilization flags.
- Historical cost changes and percentage variances.
- Flags for cost changes meeting the configured threshold.
- Review recommendations for underutilized resources.
- Estimated cost exposure for investigation.
- Warnings when history is insufficient for comparison.

## Interpretation and Limitations

- Low utilization does not prove that a resource is unnecessary.
- Cost exposure is a heuristic for prioritizing review, not guaranteed savings.
- Cost variance flags identify changes for investigation; they do not establish
  a statistical anomaly or its cause.
- At least two historical periods are needed to compare costs.
- A percentage change cannot be calculated from a previous cost of zero.
- Historical comparisons follow the order provided by the caller.
- No trained prediction model, database, frontend, or live business integration
  is included.
- Evaluation against real business data remains pending.

## Testing

From the repository root:

`python -m pytest tests -v`


## Evaluation

The current implementation uses deterministic, rule-based calculations rather
than a trained machine-learning model. Therefore, model-performance metrics
such as accuracy, precision, recall, and F1-score are not applicable to the
current version.

Validation is currently covered by automated unit and API tests for cost and
utilization calculations, historical cost variance, threshold handling,
invalid inputs, and error responses. The full current test suite contains 21
tests.

Evaluation against real business data has not been performed because no real
business dataset is included. Before production use, the module should be
evaluated with an approved dataset using business-relevant measures such as
the correctness of cost calculations, the usefulness of flagged variances,
and the reviewability of resource-saving opportunities.
