# Sales & Revenue Forecasting Module (`sales_revenue_forecasting`)

## 1. Overview

The **Sales & Revenue Forecasting** module provides time-series revenue projections and driver analysis for the IntelliOps platform. It empowers business stakeholders to forecast upcoming sales volumes and revenues, evaluate growth trajectories, account for planned scenario interventions (seasonality, marketing investments, and discount policies), and receive empirical prediction intervals.

## 2. API Contract

- **Endpoint:** `POST /api/v1/predict/sales_revenue_forecasting`
- **Method:** `POST`
- **Content-Type:** `application/json`
- **Use-Case Identifier:** `sales_revenue_forecasting`

### Request Format

```json
{
  "use_case": "sales_revenue_forecasting",
  "request_id": "req-001",
  "input": {
    "historical_sales": [12000.0, 13500.0, 12800.0, 14200.0, 15100.0, 14800.0],
    "forecast_horizon_months": 3,
    "marketing_budget": 5000.0,
    "seasonality_factor": 1.1,
    "discount_rate_pct": 5.0
  },
  "options": {
    "include_explanation": true
  }
}
```

#### Field Specifications & Constraints
- `use_case` (string, required): Must strictly equal `"sales_revenue_forecasting"`.
- `request_id` (string, optional): Client trace identifier, echoed back in the response.
- `input.historical_sales` (list of floats, required): Chronological sequence of historical revenue figures. Minimum 3 observations required. All values must be non-negative and finite.
- `input.forecast_horizon_months` (integer, optional, default: 3): Number of future months to project (1 to 24).
- `input.marketing_budget` (float, optional, default: 0.0): Planned marketing budget for the forecast horizon. Must be >= 0.0.
- `input.seasonality_factor` (float, optional, default: 1.0): Multiplicative seasonal index (> 0.0 and <= 5.0).
- `input.discount_rate_pct` (float, optional, default: 0.0): Planned average discount percentage (0.0 to 100.0).
- `options.include_explanation` (boolean, optional, default: false): Requests narrative key factor breakdown.

### Successful Response Format (`200 OK`)

```json
{
  "success": true,
  "use_case": "sales_revenue_forecasting",
  "request_id": "req-001",
  "prediction": {
    "total_forecasted_revenue": 48215.42,
    "projected_growth_rate_pct": 5.84,
    "forecast_breakdown": [
      {
        "period": "Month 1",
        "forecasted_revenue": 15721.25,
        "base_revenue": 15320.0,
        "lower_bound": 14210.15,
        "upper_bound": 17232.35
      },
      {
        "period": "Month 2",
        "forecasted_revenue": 16120.45,
        "base_revenue": 15910.0,
        "lower_bound": 14450.20,
        "upper_bound": 17790.70
      },
      {
        "period": "Month 3",
        "forecasted_revenue": 16373.72,
        "base_revenue": 16500.0,
        "lower_bound": 14580.10,
        "upper_bound": 18167.34
      }
    ],
    "trend_slope_per_period": 590.0,
    "metrics": {
      "in_sample_mae": 340.5,
      "in_sample_rmse": 412.2,
      "observations_count": 6
    }
  },
  "explanation": {
    "summary": "Projected total revenue is $48,215.42 over 3 month(s) reflecting a +5.8% average shift versus the recent historical period. Historical trajectory shows a upward slope.",
    "key_factors": [
      {
        "factor": "Baseline Trend Trajectory",
        "impact": "Upward trend of +590.00 per period (in-sample MAE: 340.50)",
        "type": "statistical_trend"
      },
      {
        "factor": "Seasonality Adjustment",
        "impact": "+10.0% multiplicative adjustment applied to base revenue",
        "type": "scenario_assumption"
      },
      {
        "factor": "Marketing Spend Allocation",
        "impact": "$5000.00 total ($1666.67/month) with estimated incremental revenue contribution",
        "type": "scenario_assumption"
      },
      {
        "factor": "Discount Pricing Impact",
        "impact": "5.0% discount rate applied with volume elasticity adjustment",
        "type": "scenario_assumption"
      }
    ]
  },
  "model": {
    "name": "Linear Trend Model with Trained Ridge Benchmark",
    "version": "1.0",
    "methodology": "OLS trend on historical inputs with empirical uncertainty intervals; validated against 6-month hold-out benchmark."
  },
  "errors": []
}
```

### Error Response Format (`400`, `422`, `500`)

```json
{
  "success": false,
  "use_case": "sales_revenue_forecasting",
  "request_id": "req-001",
  "prediction": null,
  "explanation": null,
  "model": null,
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "field": "input.historical_sales",
      "message": "At least 3 historical sales values are required."
    }
  ]
}
```

---

## 3. Forecasting Methodology & Model Design

### Handling Short Historical Series (Small Data Regime)
For payloads containing small historical sample sizes (such as the 6 observations in the project contract example), complex non-linear machine learning ensembles severely overfit.

To ensure statistical validity without claiming false precision:
1. **Trend Estimation**: The module fits an Ordinary Least Squares (OLS) linear trend on the chronological time index $t \in [0, \dots, n-1]$.
2. **Empirical Uncertainty Bands**: Standard errors for each forecast horizon $h$ are computed from the historical residual variance:
   $$SE_h = s_e \sqrt{1 + \frac{1}{n} + \frac{(t_{n-1+h} - \bar{t})^2}{\sum (t_i - \bar{t})^2}}$$
   Yielding empirical 95% prediction intervals $[y_{\text{lower}}, y_{\text{upper}}]$.
3. **Transparent Scenario Modifiers**:
   Scenario adjustments (seasonality, marketing spend, discount rate) are applied and reported explicitly:
   - **Seasonality**: Multiplicative multiplier on base projected volume.
   - **Marketing Contribution**: Diminishing-returns short-term revenue response allocated across horizon periods.
   - **Discount Rate**: Price reduction factor paired with volume elasticity adjustment.
   The output separates `base_revenue` (the pure statistical trend projection) from `forecasted_revenue` (the scenario-adjusted forecast) so stakeholders have full visibility.

### Offline Benchmark Model & Chronological Validation
When larger historical records are available, the training pipeline in `modules/sales_revenue_forecasting/train.py` trains a regularized regression pipeline (`Ridge` with `StandardScaler`):
- **Features**: Lagged sales (`lag_1`, `lag_2`), rolling average (`rolling_mean_3`), marketing budget, seasonality index, discount rate.
- **Validation**: Strictly chronological hold-out validation (28 months train, 6 months test — no random splitting and no future data leakage).
- **Benchmark Performance**: Test MAE = 390.44, Test RMSE = 412.73, Test $R^2$ = 0.9358.
- **Artifact**: Serialized to `modules/sales_revenue_forecasting/sales_model.joblib`.

---

## 4. Module Architecture

```text
modules/sales_revenue_forecasting/
├── __init__.py           # Package exports (forecast_sales_revenue)
├── schemas.py            # Pydantic V2 request & response schemas
├── preprocessing.py      # Series validation and time-series feature engineering
├── model.py              # TimeSeriesTrendForecaster and artifact loader
├── train.py              # Chronological model training & validation pipeline
├── service.py            # Decoupled core business logic
├── router.py             # FastAPI APIRouter mounting POST /api/v1/predict/sales_revenue_forecasting
├── sales_model.joblib    # Serialized benchmark model artifact
└── README.md             # Module documentation
```

---

## 5. Dataset Source

The demonstration and benchmark dataset is located at:
`data/sample_monthly_sales.csv`

> [!NOTE]
> This is a clearly labeled synthetic sample dataset representing 36 months of retail/e-commerce sales. It is **not** real proprietary company data.

---

## 6. Running Tests & Training

Activate your virtual environment and execute:

### Run Model Training:
```bash
python -m modules.sales_revenue_forecasting.train
```

### Run Unit and API Tests:
```bash
python -m pytest tests/test_sales_revenue_forecasting.py tests/test_sales_revenue_forecasting_api.py -v
```

---

## 7. Limitations & Integration Notes

- **Current Application Integration**: The module provides an isolated `APIRouter` in `router.py`. Because the shared FastAPI backend entry point (`backend/main.py`) has not yet been initialized in `develop`, mounting the router into the shared app will occur when the backend integration is performed:
  ```python
  from modules.sales_revenue_forecasting.router import router as sales_revenue_router
  app.include_router(sales_revenue_router)
  ```
- **Frontend Integration**: The React frontend currently contains only placeholder files. Frontend integration will follow once the shared frontend routing and layout are initialized.
- **Small Historical Samples**: Series shorter than 3 periods are rejected. With series under 12 periods, seasonality cannot be inferred statistically from data alone and must be supplied as a scenario factor.
