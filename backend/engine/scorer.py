from typing import List, Tuple
from backend.models import HealthScore, DatasetSummary, ColumnProfile

def calculate_health_score(summary: DatasetSummary, columns: List[ColumnProfile]) -> HealthScore:
    """
    Compute a deterministic Data Quality Health Score between 0 and 100.
    Components:
      - Completeness (35 pts): Ratio of populated cells.
      - Uniqueness (25 pts): Absence of duplicate rows and presence of candidate keys.
      - Validity & Outlier (25 pts): Low proportion of extreme outliers and anomalous values.
      - Consistency (15 pts): Absence of type mismatches or corrupted values.
    """
    findings: List[str] = []
    recommendations: List[str] = []

    # 1. Completeness Score (0-35)
    missing_pct = summary.overall_missing_percentage
    completeness_ratio = max(0.0, 1.0 - (missing_pct / 100.0))
    completeness_score = round(completeness_ratio * 35.0, 1)

    if missing_pct > 20.0:
        findings.append(f"High data missingness: {missing_pct:.1f}% of total cells are null.")
        recommendations.append("Investigate data pipeline sources for missing data or apply imputation strategies.")
    elif missing_pct > 5.0:
        findings.append(f"Moderate missingness: {missing_pct:.1f}% of total cells are null.")
    else:
        findings.append(f"Strong completeness: Only {missing_pct:.1f}% of cells are null.")

    # 2. Uniqueness Score (0-25)
    dup_pct = summary.duplicate_rows_percentage
    dup_penalty = min(20.0, (dup_pct / 100.0) * 40.0)
    has_candidate_key = len(summary.candidate_primary_keys) > 0
    key_bonus = 5.0 if has_candidate_key else 0.0
    uniqueness_score = round(max(0.0, 20.0 - dup_penalty) + key_bonus, 1)

    if dup_pct > 5.0:
        findings.append(f"Duplicate records detected: {summary.duplicate_rows_count} rows ({dup_pct:.1f}%).")
        recommendations.append("Execute deduplication using primary identifiers before downstream processing.")
    elif dup_pct > 0.0:
        findings.append(f"Minor duplicate count: {summary.duplicate_rows_count} duplicate row(s).")
    else:
        findings.append("Zero duplicate rows detected across the dataset.")

    if not has_candidate_key:
        findings.append("No single-column candidate primary key identified (no column is 100% unique & non-null).")
        recommendations.append("Verify composite key constraints or synthesize a surrogate primary key identifier.")
    else:
        keys_str = ", ".join(summary.candidate_primary_keys[:3])
        findings.append(f"Identified candidate primary key(s): {keys_str}.")

    # 3. Validity & Outliers (0-25)
    total_numeric_cols = 0
    total_outlier_pct_sum = 0.0
    outlier_flagged_cols = []

    for col in columns:
        if col.outliers and col.outliers.iqr_outlier_count > 0:
            total_numeric_cols += 1
            total_outlier_pct_sum += col.outliers.iqr_outlier_percentage
            if col.outliers.iqr_outlier_percentage > 5.0:
                outlier_flagged_cols.append(col.name)

    if total_numeric_cols > 0:
        avg_outlier_pct = total_outlier_pct_sum / total_numeric_cols
        outlier_penalty = min(25.0, avg_outlier_pct * 1.5)
        validity_score = round(max(0.0, 25.0 - outlier_penalty), 1)
        if outlier_flagged_cols:
            cols_str = ", ".join(outlier_flagged_cols[:3])
            findings.append(f"Elevated outlier density detected in columns: {cols_str}.")
            recommendations.append("Review statistical outliers for data entry anomalies, extreme sensor noise, or distribution shifts.")
    else:
        validity_score = 25.0

    # 4. Consistency & Issues (0-15)
    columns_with_issues = [c for c in columns if len(c.issues) > 0]
    issues_count = sum(len(c.issues) for c in columns)
    consistency_penalty = min(15.0, issues_count * 2.0)
    consistency_score = round(max(0.0, 15.0 - consistency_penalty), 1)

    if columns_with_issues:
        findings.append(f"{len(columns_with_issues)} column(s) exhibit type ambiguity or formatting anomalies.")
        recommendations.append("Standardize column types and format conventions (e.g. date parsing, string trim).")
    else:
        findings.append("All column data types demonstrate structural consistency.")

    # Total Score
    total_score = round(completeness_score + uniqueness_score + validity_score + consistency_score, 1)
    total_score = max(0.0, min(100.0, total_score))

    # Grade
    if total_score >= 90.0:
        grade = "A"
    elif total_score >= 80.0:
        grade = "B"
    elif total_score >= 70.0:
        grade = "C"
    elif total_score >= 60.0:
        grade = "D"
    else:
        grade = "F"

    if not recommendations:
        recommendations.append("Dataset adheres to optimal quality standards. No immediate remediation required.")

    return HealthScore(
        overall_score=total_score,
        grade=grade,
        completeness_score=completeness_score,
        uniqueness_score=uniqueness_score,
        validity_score=validity_score,
        consistency_score=consistency_score,
        summary_findings=findings,
        recommendations=recommendations
    )
