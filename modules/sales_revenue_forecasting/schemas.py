from typing import Any
from pydantic import BaseModel, Field, field_validator


class SalesRevenueInput(BaseModel):
    historical_sales: list[float] = Field(
        ...,
        min_length=3,
        description="Chronological series of past sales/revenue figures (at least 3 values).",
    )
    forecast_horizon_months: int = Field(
        default=3,
        ge=1,
        le=24,
        description="Number of forward months/periods to forecast (1 to 24).",
    )
    marketing_budget: float = Field(
        default=0.0,
        ge=0.0,
        description="Planned marketing budget for the forecast period (non-negative).",
    )
    seasonality_factor: float = Field(
        default=1.0,
        gt=0.0,
        le=5.0,
        description="Multiplicative seasonality factor (e.g. 1.0 for neutral, 1.15 for peak season).",
    )
    discount_rate_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Planned average discount percentage (0 to 100).",
    )

    @field_validator("historical_sales")
    @classmethod
    def validate_historical_sales(cls, v: list[float]) -> list[float]:
        if len(v) < 3:
            raise ValueError("At least 3 historical sales values are required.")
        for idx, val in enumerate(v):
            if val < 0.0:
                raise ValueError(
                    f"Historical sales values cannot be negative. Found {val} at index {idx}."
                )
        return v


class PredictionOptions(BaseModel):
    include_explanation: bool = Field(
        default=False,
        description="Whether to generate an analytical narrative breakdown of forecast drivers.",
    )


class PredictionRequest(BaseModel):
    use_case: str = Field(
        ...,
        description="Module identifier, must be 'sales_revenue_forecasting'.",
    )
    request_id: str | None = Field(
        default=None,
        description="Optional request identifier for end-to-end tracing.",
    )
    input: SalesRevenueInput
    options: PredictionOptions = Field(default_factory=PredictionOptions)


class PeriodForecast(BaseModel):
    period: str
    forecasted_revenue: float
    base_revenue: float
    lower_bound: float
    upper_bound: float


class ModelMetrics(BaseModel):
    in_sample_mae: float
    in_sample_rmse: float
    observations_count: int


class SalesRevenuePrediction(BaseModel):
    total_forecasted_revenue: float
    projected_growth_rate_pct: float
    forecast_breakdown: list[PeriodForecast]
    trend_slope_per_period: float
    metrics: ModelMetrics


class KeyFactor(BaseModel):
    factor: str
    impact: str
    type: str = "driver"


class PredictionExplanation(BaseModel):
    summary: str
    key_factors: list[KeyFactor] = Field(default_factory=list)


class ModelMetadata(BaseModel):
    name: str
    version: str
    methodology: str


class ErrorItem(BaseModel):
    code: str
    field: str | None = None
    message: str


class StandardResponse(BaseModel):
    success: bool
    use_case: str
    request_id: str | None
    prediction: SalesRevenuePrediction | None = None
    explanation: PredictionExplanation | None = None
    model: ModelMetadata | None = None
    errors: list[ErrorItem] = Field(default_factory=list)
