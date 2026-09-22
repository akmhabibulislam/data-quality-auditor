from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class OutlierMetrics(BaseModel):
    iqr_multiplier: float = 1.5
    iqr_lower_bound: Optional[float] = None
    iqr_upper_bound: Optional[float] = None
    iqr_outlier_count: int = 0
    iqr_outlier_percentage: float = 0.0
    
    zscore_threshold: float = 3.0
    zscore_outlier_count: int = 0
    zscore_outlier_percentage: float = 0.0
    
    # Robust Z-Score via Median Absolute Deviation (MAD)
    robust_zscore_outlier_count: int = 0
    robust_zscore_outlier_percentage: float = 0.0

class NumericStats(BaseModel):
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    q25: Optional[float] = None
    median: Optional[float] = None
    q75: Optional[float] = None
    max: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    distribution_shape: str = "Normal"  # Normal, Left-Skewed, Right-Skewed, Heavy-Tailed
    zeros_count: int = 0
    zeros_percentage: float = 0.0

class ColumnProfile(BaseModel):
    name: str
    physical_type: str
    inferred_type: str
    total_count: int
    missing_count: int
    missing_percentage: float
    unique_count: int
    unique_percentage: float
    is_candidate_key: bool = False
    sample_values: List[Any] = Field(default_factory=list)
    top_frequencies: List[Dict[str, Any]] = Field(default_factory=list)
    numeric_stats: Optional[NumericStats] = None
    outliers: Optional[OutlierMetrics] = None
    issues: List[str] = Field(default_factory=list)

class MissingPatternAssessment(BaseModel):
    overall_null_rate: float
    mechanism_hypothesis: str  # "MCAR (Missing Completely at Random)", "MAR (Missing at Random - Correlated)", "None"
    correlated_missing_pairs: List[Dict[str, Any]] = Field(default_factory=list)
    description: str

class DatasetSummary(BaseModel):
    filename: str
    file_size_bytes: int
    file_format: str
    row_count: int
    column_count: int
    total_cells: int
    total_missing_cells: int
    overall_missing_percentage: float
    duplicate_rows_count: int
    duplicate_rows_percentage: float
    memory_usage_bytes: int
    candidate_primary_keys: List[str] = Field(default_factory=list)

class RemediationPlan(BaseModel):
    summary_actions: List[str] = Field(default_factory=list)
    polars_code: str
    sql_code: str

class HealthScore(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=100.0)
    grade: str
    completeness_score: float
    uniqueness_score: float
    validity_score: float
    consistency_score: float
    summary_findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

class AuditConfig(BaseModel):
    iqr_multiplier: float = Field(default=1.5, ge=0.5, le=5.0)
    zscore_threshold: float = Field(default=3.0, ge=1.0, le=6.0)

class AuditReport(BaseModel):
    timestamp: str
    config: AuditConfig
    summary: DatasetSummary
    health_score: HealthScore
    missing_analysis: MissingPatternAssessment
    remediation: RemediationPlan
    columns: List[ColumnProfile]
    preview_rows: List[Dict[str, Any]] = Field(default_factory=list)
