import re
from datetime import datetime
from typing import List, Dict, Any, Tuple
import polars as pl

from backend.models import ColumnProfile, DatasetSummary, AuditReport, AuditConfig
from backend.engine.anomaly import calculate_numeric_stats, calculate_outliers, assess_missingness_mechanism
from backend.engine.scorer import calculate_health_score
from backend.engine.remediation import generate_remediation_plan

def infer_semantic_type(series: pl.Series) -> str:
    """Infer logical semantic data type from Polars series."""
    valid_series = series.drop_nulls()
    if valid_series.len() == 0:
        return "Empty / Unknown"

    if series.dtype.is_numeric():
        if series.dtype.is_integer():
            return "Integer"
        return "Float"

    if series.dtype == pl.Boolean:
        return "Boolean"

    if series.dtype in (pl.Date, pl.Datetime):
        return "DateTime"

    # Sample check for string / object types
    sample_values = [str(x).strip() for x in valid_series.head(100).to_list()]
    
    # Check boolean representation
    bool_set = {"true", "false", "0", "1", "yes", "no", "y", "n", "t", "f"}
    if all(val.lower() in bool_set for val in sample_values if val):
        return "Boolean (String-Encoded)"

    # Check numeric representation
    num_pattern = re.compile(r"^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$")
    if all(num_pattern.match(val) for val in sample_values if val):
        return "Numeric (String-Encoded)"

    # Check date patterns
    date_patterns = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{4}/\d{2}/\d{2}$",
        r"^\d{2}/\d{2}/\d{4}$",
        r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
    ]
    if any(all(re.match(p, val) for val in sample_values if val) for p in date_patterns):
        return "DateTime (String-Encoded)"

    # Check cardinality
    unique_cnt = series.n_unique()
    total_cnt = series.len()
    if total_cnt > 20 and (unique_cnt / total_cnt) < 0.15:
        return "Categorical"

    return "Text / String"

def profile_dataset(
    df: pl.DataFrame, 
    filename: str, 
    file_size_bytes: int, 
    file_format: str,
    config: AuditConfig = AuditConfig()
) -> AuditReport:
    """Run comprehensive vectorized profiling, pattern detection, and remediation planning."""
    row_count = df.height
    col_count = df.width
    total_cells = row_count * col_count
    
    # Missing cells calculation
    null_counts = df.null_count()
    total_missing = sum(null_counts.row(0)) if row_count > 0 and col_count > 0 else 0
    overall_missing_pct = round((total_missing / total_cells * 100.0), 2) if total_cells > 0 else 0.0

    # Duplicate rows detection
    duplicate_rows_count = 0
    duplicate_rows_pct = 0.0
    if row_count > 0:
        unique_rows_count = df.unique().height
        duplicate_rows_count = row_count - unique_rows_count
        duplicate_rows_pct = round((duplicate_rows_count / row_count * 100.0), 2)

    memory_usage_bytes = df.estimated_size()
    candidate_primary_keys: List[str] = []
    columns_profile: List[ColumnProfile] = []

    for col_name in df.columns:
        series = df[col_name]
        total_cnt = series.len()
        null_cnt = series.null_count()
        missing_pct = round((null_cnt / total_cnt * 100.0), 2) if total_cnt > 0 else 0.0
        unique_cnt = series.n_unique()
        unique_pct = round((unique_cnt / total_cnt * 100.0), 2) if total_cnt > 0 else 0.0

        is_cand_key = (null_cnt == 0) and (unique_cnt == total_cnt) and (total_cnt > 0)
        if is_cand_key:
            candidate_primary_keys.append(col_name)

        inferred = infer_semantic_type(series)

        sample_vals = [
            x if x is not None else None 
            for x in series.drop_nulls().head(5).to_list()
        ]

        top_freqs: List[Dict[str, Any]] = []
        try:
            vc = series.value_counts(sort=True).head(5)
            for row in vc.iter_rows():
                top_freqs.append({"value": str(row[0]), "count": int(row[1])})
        except Exception:
            pass

        num_stats = calculate_numeric_stats(series)
        outliers = calculate_outliers(
            series=series, 
            num_stats=num_stats,
            iqr_multiplier=config.iqr_multiplier,
            zscore_threshold=config.zscore_threshold
        )

        issues: List[str] = []
        if missing_pct > 30.0:
            issues.append(f"Severe missing rate ({missing_pct}%).")
        elif missing_pct > 10.0:
            issues.append(f"Moderate missing rate ({missing_pct}%).")

        if "String-Encoded" in inferred:
            issues.append(f"Mixed / uncast data: Stored as text instead of {inferred}.")

        if outliers and outliers.iqr_outlier_count > 0:
            if outliers.iqr_outlier_percentage > 5.0:
                issues.append(f"High statistical anomaly rate: {outliers.iqr_outlier_count} IQR outliers ({outliers.iqr_outlier_percentage}%).")

        if unique_cnt == 1 and total_cnt > 1:
            issues.append("Constant column: Zero variance across all records.")

        profile = ColumnProfile(
            name=col_name,
            physical_type=str(series.dtype),
            inferred_type=inferred,
            total_count=total_cnt,
            missing_count=null_cnt,
            missing_percentage=missing_pct,
            unique_count=unique_cnt,
            unique_percentage=unique_pct,
            is_candidate_key=is_cand_key,
            sample_values=sample_vals,
            top_frequencies=top_freqs,
            numeric_stats=num_stats,
            outliers=outliers,
            issues=issues
        )
        columns_profile.append(profile)

    summary = DatasetSummary(
        filename=filename,
        file_size_bytes=file_size_bytes,
        file_format=file_format,
        row_count=row_count,
        column_count=col_count,
        total_cells=total_cells,
        total_missing_cells=total_missing,
        overall_missing_percentage=overall_missing_pct,
        duplicate_rows_count=duplicate_rows_count,
        duplicate_rows_percentage=duplicate_rows_pct,
        memory_usage_bytes=memory_usage_bytes,
        candidate_primary_keys=candidate_primary_keys
    )

    health_score = calculate_health_score(summary, columns_profile)
    missing_analysis = assess_missingness_mechanism(df)
    remediation = generate_remediation_plan(summary, columns_profile)

    preview_df = df.head(15)
    preview_rows = preview_df.to_dicts()

    return AuditReport(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        config=config,
        summary=summary,
        health_score=health_score,
        missing_analysis=missing_analysis,
        remediation=remediation,
        columns=columns_profile,
        preview_rows=preview_rows
    )
