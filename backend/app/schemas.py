from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

BUSINESS_CATEGORIES = [
    "Restaurant", "Cafe", "Grocery Store", "Clothing Store", "Pharmacy",
    "Bakery", "Gym", "Electronics Store", "Salon", "Stationery Store",
    "Bookstore", "Healthcare Clinic", "Coworking Space", "Hotel / Hospitality",
    "Warehouse & Logistics", "Jewelry & Accessories", "Automobile Service",
    "Hardware & Tools", "Entertainment & Gaming", "Other"
]

class BusinessProfile(BaseModel):
    business_name: str = Field(default="My Business", max_length=120)
    category: str = Field(default="Restaurant", max_length=120)
    target_customer: str = Field(default="General public", max_length=120)
    budget: float = Field(gt=0, description="Monthly budget for rent and operating costs")
    preferred_city: str = Field(default="", max_length=120)
    required_space_sqm: Optional[float] = Field(default=None, ge=0)
    parking_required: bool = False

    @field_validator("category")
    @classmethod
    def category_supported(cls, value):
        val = str(value).strip()
        if not val:
            raise ValueError("Business category cannot be empty.")
        return val

    @field_validator("required_space_sqm", mode="before")
    @classmethod
    def parse_optional_space(cls, value):
        if value is None or value == "" or str(value).strip() == "":
            return None
        return float(value)

class CandidateLocation(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    area: str = Field(min_length=1, max_length=120)
    city: str = Field(default="", max_length=120)
    footfall: Optional[float] = Field(default=None, ge=0)
    demand: Optional[float] = Field(default=None, ge=0, le=100)
    competition: Optional[float] = Field(default=None, ge=0, le=100)
    monthly_rent: Optional[float] = Field(default=None, ge=0)
    operating_cost: Optional[float] = Field(default=None, ge=0)
    accessibility: Optional[float] = Field(default=None, ge=0, le=100)
    parking: Optional[bool] = None
    infrastructure: Optional[float] = Field(default=None, ge=0, le=100)
    target_match: Optional[float] = Field(default=None, ge=0, le=100)
    space_sqm: Optional[float] = Field(default=None, ge=0)

    @field_validator(
        "footfall", "demand", "competition", "monthly_rent", "operating_cost",
        "accessibility", "infrastructure", "target_match", "space_sqm",
        mode="before"
    )
    @classmethod
    def parse_optional_numeric(cls, value):
        if value is None or value == "" or str(value).strip() == "":
            return None
        return float(value)

class LocationAnalysisRequest(BaseModel):
    profile: BusinessProfile
    locations: List[CandidateLocation] = Field(min_length=2, max_length=100)
    weights: Dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_locations(self):
        ids = [loc.id for loc in self.locations]
        if len(ids) != len(set(ids)):
            raise ValueError("Candidate location IDs must be unique.")
        names = [(loc.name.strip().lower(), loc.area.strip().lower()) for loc in self.locations]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate candidate locations detected. Use distinct names/areas.")
        return self

class ScenarioRequest(LocationAnalysisRequest):
    """What-if scenario evaluation request, sharing the same schema and validation as LocationAnalysisRequest."""
    pass

class FactorResult(BaseModel):
    key: str
    label: str
    raw_value: Optional[float | bool]
    utility_score: Optional[float]
    weight: float
    contribution: Optional[float]
    direction: str

class LocationRecommendation(BaseModel):
    id: str
    name: str
    area: str
    city: str
    rank: int
    score: float
    classification: str
    data_completeness: float
    factors: List[FactorResult]
    strengths: List[str]
    weaknesses: List[str]
    warnings: List[str]
    next_steps: List[str]
    cost_total: Optional[float]
    space_sqm: Optional[float] = None

class AnalysisMetadata(BaseModel):
    method: str
    method_version: str
    analysis_timestamp: str
    locations_evaluated: int
    disclaimer: str

class AnalysisResponse(BaseModel):
    recommendations: List[LocationRecommendation]
    metadata: AnalysisMetadata
    normalized_weights: Dict[str, float]


# ---------------------------------------------------------------------------
# Schemas for Section 4.1: Location — Default Recommendations
# ---------------------------------------------------------------------------

class DefaultCategoryItem(BaseModel):
    id: str
    name: str
    environment: str
    description: str
    footfall_level: float
    accessibility_level: float
    competition_density: float
    typical_cost_tier: str
    typical_monthly_cost: float
    parking_support: str
    primary_customer_segments: List[str]

class DefaultRecommendationFactor(BaseModel):
    key: str
    label: str
    utility_score: float
    weight: float
    direction: str

class DefaultRecommendationItem(BaseModel):
    id: str
    name: str
    category_name: str
    environment: str
    rank: int
    score: float
    classification: str
    description: str
    factors: List[DefaultRecommendationFactor]
    strengths: List[str]
    weaknesses: List[str]
    warnings: List[str]
    next_steps: List[str]
    typical_cost_estimate: float
    customer_segments: List[str]
    methodology_note: str

class DefaultAnalysisRequest(BaseModel):
    business_type: str = Field(default="Restaurant")
    profile: Optional[BusinessProfile] = None
    weights: Optional[Dict[str, float]] = None
    environments: Optional[List[str]] = None

class DefaultAnalysisResponse(BaseModel):
    recommendations: List[DefaultRecommendationItem]
    total_categories_evaluated: int
    business_type: str
    metadata: AnalysisMetadata

class DefaultScenarioRequest(DefaultAnalysisRequest):
    """What-if scenario on default recommendations."""
    pass


# ---------------------------------------------------------------------------
# Schemas for Section 4.2: Location — Based on Your Data Input
# ---------------------------------------------------------------------------

class DatasetColumnInfo(BaseModel):
    name: str
    original_name: str
    inferred_type: str
    non_null_count: int
    unique_count: int
    sample_values: List[str]

class DatasetInspectionSummary(BaseModel):
    dataset_id: str
    filename: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    rejected_reasons: List[str]
    columns: List[DatasetColumnInfo]
    mandatory_columns_found: Dict[str, str]
    optional_columns_found: List[str]
    available_business_types: List[str]
    unique_locations_count: int
    warnings: List[str]

class CustomUploadResponse(BaseModel):
    summary: DatasetInspectionSummary
    rows: List[Dict[str, Any]]
    preview: List[Dict[str, Any]]

class CustomEvidenceRecord(BaseModel):
    row_index: int
    location_name: str
    business_type: str
    additional_data: Dict[str, Any]

class CustomRecommendationItem(BaseModel):
    id: str
    rank: int
    location_name: str
    business_type: str
    score: float
    classification: str
    occurrence_count: int
    total_business_records: int
    association_percentage: float
    co_located_business_types: List[str]
    numeric_metrics: Dict[str, float]
    text_metrics: Dict[str, str]
    strengths: List[str]
    weaknesses: List[str]
    warnings: List[str]
    next_steps: List[str]
    evidence_records: List[CustomEvidenceRecord]

class CustomAnalysisRequest(BaseModel):
    dataset_id: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    selected_business_type: str
    min_occurrences: int = 1
    weight_frequency: float = 0.6
    weight_metrics: float = 0.4
    budget_filter: Optional[float] = None
    metric_overrides: Optional[Dict[str, Dict[str, float]]] = None

class CustomAnalysisResponse(BaseModel):
    recommendations: List[CustomRecommendationItem]
    selected_business_type: str
    total_locations_recommended: int
    dataset_summary: DatasetInspectionSummary
    metadata: AnalysisMetadata

class CustomScenarioRequest(CustomAnalysisRequest):
    """What-if scenario evaluation on user dataset."""
    pass
