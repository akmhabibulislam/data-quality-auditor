from typing import List
from backend.models import ColumnProfile, DatasetSummary, RemediationPlan

def generate_remediation_plan(summary: DatasetSummary, columns: List[ColumnProfile]) -> RemediationPlan:
    """
    Generate production-ready executable Python/Polars and ANSI SQL remediation code
    based on automated diagnostic discoveries.
    """
    actions: List[str] = []
    polars_lines: List[str] = [
        "import polars as pl",
        "",
        "# Load target dataset",
        f"df = pl.read_csv('{summary.filename}')",
        ""
    ]
    sql_lines: List[str] = [
        "-- Automated Remediation View Definition",
        "WITH clean_base AS (",
        f"    SELECT * FROM {summary.filename.split('.')[0] or 'dataset'}"
    ]

    # 1. Deduplication
    if summary.duplicate_rows_count > 0:
        actions.append(f"Execute unique row deduplication (drops {summary.duplicate_rows_count} duplicate rows).")
        polars_lines.append("# Deduplication")
        polars_lines.append("df = df.unique()")
        polars_lines.append("")

    # 2. Type casting for string-encoded types
    cast_exprs = []
    for col in columns:
        if "Numeric (String-Encoded)" in col.inferred_type:
            actions.append(f"Cast '{col.name}' from String to Float64.")
            cast_exprs.append(f"pl.col('{col.name}').cast(pl.Float64, strict=False)")
        elif "DateTime (String-Encoded)" in col.inferred_type:
            actions.append(f"Parse '{col.name}' as Datetime.")
            cast_exprs.append(f"pl.col('{col.name}').str.to_datetime(strict=False)")
        elif "Boolean (String-Encoded)" in col.inferred_type:
            actions.append(f"Cast '{col.name}' to Boolean.")
            cast_exprs.append(f"pl.col('{col.name}').cast(pl.Boolean, strict=False)")

    if cast_exprs:
        polars_lines.append("# Standardize and cast corrupted data types")
        polars_lines.append(f"df = df.with_columns([\n    " + ",\n    ".join(cast_exprs) + "\n])")
        polars_lines.append("")

    # 3. Imputation Strategy
    impute_exprs = []
    for col in columns:
        if col.missing_percentage > 0:
            if col.numeric_stats:
                if col.numeric_stats.skewness and abs(col.numeric_stats.skewness) > 1.0:
                    actions.append(f"Impute '{col.name}' with median ({col.numeric_stats.median}) due to heavy skewness.")
                    impute_exprs.append(f"pl.col('{col.name}').fill_null(pl.col('{col.name}').median())")
                else:
                    actions.append(f"Impute '{col.name}' with column mean ({col.numeric_stats.mean}).")
                    impute_exprs.append(f"pl.col('{col.name}').fill_null(pl.col('{col.name}').mean())")
            else:
                top_val = col.top_frequencies[0]["value"] if col.top_frequencies else "UNKNOWN"
                actions.append(f"Impute categorical '{col.name}' with mode ('{top_val}').")
                impute_exprs.append(f"pl.col('{col.name}').fill_null('{top_val}')")

    if impute_exprs:
        polars_lines.append("# Handle missing values via strategy-derived imputation")
        polars_lines.append(f"df = df.with_columns([\n    " + ",\n    ".join(impute_exprs) + "\n])")
        polars_lines.append("")

    # 4. Outlier clipping
    clip_exprs = []
    for col in columns:
        if col.outliers and col.outliers.iqr_outlier_count > 0 and col.outliers.iqr_lower_bound is not None:
            actions.append(f"Clip extreme statistical outliers on '{col.name}' to IQR bounds [{col.outliers.iqr_lower_bound}, {col.outliers.iqr_upper_bound}].")
            clip_exprs.append(
                f"pl.col('{col.name}').clip({col.outliers.iqr_lower_bound}, {col.outliers.iqr_upper_bound})"
            )

    if clip_exprs:
        polars_lines.append("# Bound extreme statistical outliers to IQR thresholds")
        polars_lines.append(f"df = df.with_columns([\n    " + ",\n    ".join(clip_exprs) + "\n])")
        polars_lines.append("")

    polars_lines.append("# Save sanitized dataset")
    polars_lines.append("df.write_parquet('sanitized_dataset.parquet')")

    # Generate SQL transformation query
    select_items = []
    for col in columns:
        col_expr = f'"{col.name}"'
        if col.missing_percentage > 0 and col.numeric_stats:
            val = col.numeric_stats.median if abs(col.numeric_stats.skewness or 0) > 1.0 else col.numeric_stats.mean
            col_expr = f'COALESCE("{col.name}", {val}) AS "{col.name}"'
        elif col.missing_percentage > 0:
            top_val = col.top_frequencies[0]["value"] if col.top_frequencies else "UNKNOWN"
            col_expr = f'COALESCE("{col.name}", \'{top_val}\') AS "{col.name}"'
        select_items.append(f"    {col_expr}")

    sql_lines.append(")")
    if summary.duplicate_rows_count > 0:
        sql_lines.append("SELECT DISTINCT")
    else:
        sql_lines.append("SELECT")
    sql_lines.append(",\n".join(select_items))
    sql_lines.append("FROM clean_base;")

    if not actions:
        actions.append("Dataset passed all structural quality thresholds. No remediation transformations required.")

    return RemediationPlan(
        summary_actions=actions,
        polars_code="\n".join(polars_lines),
        sql_code="\n".join(sql_lines)
    )
