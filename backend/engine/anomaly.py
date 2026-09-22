import math
from typing import Optional, Tuple, List, Dict, Any
import polars as pl
import numpy as np
from scipy import stats as sp_stats

from backend.models import OutlierMetrics, NumericStats, MissingPatternAssessment

def calculate_numeric_stats(series: pl.Series) -> Optional[NumericStats]:
    """Calculate descriptive statistics, skewness, and kurtosis for numeric series."""
    valid_series = series.drop_nulls()
    if valid_series.len() == 0 or not series.dtype.is_numeric():
        return None

    f_series = valid_series.cast(pl.Float64)
    total_valid = f_series.len()
    
    mean_val = f_series.mean()
    std_val = f_series.std()
    min_val = f_series.min()
    max_val = f_series.max()
    
    q25 = f_series.quantile(0.25, interpolation="linear")
    median_val = f_series.median()
    q75 = f_series.quantile(0.75, interpolation="linear")

    zeros_count = (f_series == 0.0).sum()
    zeros_pct = round((zeros_count / total_valid * 100.0), 2) if total_valid > 0 else 0.0

    skew_val = None
    kurt_val = None
    dist_shape = "Normal"

    if total_valid >= 4 and std_val is not None and std_val > 0:
        try:
            arr = f_series.to_numpy()
            raw_skew = float(sp_stats.skew(arr, bias=False))
            if not (math.isnan(raw_skew) or math.isinf(raw_skew)):
                skew_val = round(raw_skew, 3)

            raw_kurt = float(sp_stats.kurtosis(arr, bias=False))
            if not (math.isnan(raw_kurt) or math.isinf(raw_kurt)):
                kurt_val = round(raw_kurt, 3)

            # Determine distribution shape classification
            if skew_val is not None:
                if skew_val > 1.0:
                    dist_shape = "Highly Right-Skewed"
                elif skew_val < -1.0:
                    dist_shape = "Highly Left-Skewed"
                elif abs(skew_val) <= 0.5:
                    if kurt_val is not None and kurt_val > 2.0:
                        dist_shape = "Heavy-Tailed (Leptokurtic)"
                    else:
                        dist_shape = "Symmetric / Normal"
                else:
                    dist_shape = "Moderately Skewed"
        except Exception:
            pass

    return NumericStats(
        mean=round(float(mean_val), 3) if mean_val is not None else None,
        std=round(float(std_val), 3) if std_val is not None else None,
        min=round(float(min_val), 3) if min_val is not None else None,
        q25=round(float(q25), 3) if q25 is not None else None,
        median=round(float(median_val), 3) if median_val is not None else None,
        q75=round(float(q75), 3) if q75 is not None else None,
        max=round(float(max_val), 3) if max_val is not None else None,
        skewness=skew_val,
        kurtosis=kurt_val,
        distribution_shape=dist_shape,
        zeros_count=int(zeros_count),
        zeros_percentage=zeros_pct
    )

def calculate_outliers(
    series: pl.Series, 
    num_stats: Optional[NumericStats], 
    iqr_multiplier: float = 1.5, 
    zscore_threshold: float = 3.0
) -> Optional[OutlierMetrics]:
    """Calculate configurable IQR, standard Z-Score, and robust MAD Z-Score outliers."""
    if num_stats is None or not series.dtype.is_numeric():
        return None

    valid_series = series.drop_nulls().cast(pl.Float64)
    total_valid = valid_series.len()
    if total_valid < 4:
        return OutlierMetrics(iqr_multiplier=iqr_multiplier, zscore_threshold=zscore_threshold)

    q25 = num_stats.q25
    q75 = num_stats.q75
    if q25 is None or q75 is None:
        return OutlierMetrics(iqr_multiplier=iqr_multiplier, zscore_threshold=zscore_threshold)

    # 1. IQR Method
    iqr = q75 - q25
    iqr_lower = round(q25 - (iqr_multiplier * iqr), 3)
    iqr_upper = round(q75 + (iqr_multiplier * iqr), 3)

    iqr_outliers = (valid_series < iqr_lower) | (valid_series > iqr_upper)
    iqr_count = int(iqr_outliers.sum())
    iqr_pct = round((iqr_count / total_valid * 100.0), 2)

    # 2. Standard Z-Score (|Z| >= threshold)
    mean_val = num_stats.mean
    std_val = num_stats.std
    z_count = 0
    z_pct = 0.0

    if std_val and std_val > 0 and mean_val is not None:
        z_outliers = ((valid_series - mean_val).abs() / std_val) >= zscore_threshold
        z_count = int(z_outliers.sum())
        z_pct = round((z_count / total_valid * 100.0), 2)

    # 3. Robust Z-Score via Median Absolute Deviation (MAD)
    # Modified Z = 0.6745 * (x - median) / MAD
    median_val = num_stats.median
    robust_count = 0
    robust_pct = 0.0

    if median_val is not None:
        abs_diff = (valid_series - median_val).abs()
        mad = abs_diff.median()
        if mad and mad > 0:
            modified_z = (0.6745 * abs_diff) / mad
            robust_outliers = modified_z >= 3.5
            robust_count = int(robust_outliers.sum())
            robust_pct = round((robust_count / total_valid * 100.0), 2)

    return OutlierMetrics(
        iqr_multiplier=iqr_multiplier,
        iqr_lower_bound=iqr_lower,
        iqr_upper_bound=iqr_upper,
        iqr_outlier_count=iqr_count,
        iqr_outlier_percentage=iqr_pct,
        zscore_threshold=zscore_threshold,
        zscore_outlier_count=z_count,
        zscore_outlier_percentage=z_pct,
        robust_zscore_outlier_count=robust_count,
        robust_zscore_outlier_percentage=robust_pct
    )

def assess_missingness_mechanism(df: pl.DataFrame) -> MissingPatternAssessment:
    """
    Perform correlation and co-occurrence analysis on null indicator matrices
    to categorize missing data patterns (MCAR vs MAR/MNAR heuristics).
    """
    total_cells = df.height * df.width
    if total_cells == 0:
        return MissingPatternAssessment(
            overall_null_rate=0.0,
            mechanism_hypothesis="None",
            correlated_missing_pairs=[],
            description="Empty dataset."
        )

    null_counts = df.null_count()
    total_missing = sum(null_counts.row(0))
    overall_null_pct = round((total_missing / total_cells * 100.0), 2)

    if total_missing == 0:
        return MissingPatternAssessment(
            overall_null_rate=0.0,
            mechanism_hypothesis="None (Complete Dataset)",
            correlated_missing_pairs=[],
            description="Zero missing values observed across all columns."
        )

    # Build boolean null indicators for columns with missing values
    cols_with_nulls = [c for c in df.columns if df[c].null_count() > 0]
    if len(cols_with_nulls) < 2:
        return MissingPatternAssessment(
            overall_null_rate=overall_null_pct,
            mechanism_hypothesis="MCAR (Missing Completely at Random)",
            correlated_missing_pairs=[],
            description="Isolated missingness in a single feature; likely random omission (MCAR)."
        )

    # Calculate Pearson phi correlation on boolean missingness flags
    correlated_pairs: List[Dict[str, Any]] = []
    has_high_correlation = False

    for i in range(len(cols_with_nulls)):
        for j in range(i + 1, len(cols_with_nulls)):
            col_a = cols_with_nulls[i]
            col_b = cols_with_nulls[j]

            # Null masks
            mask_a = df[col_a].is_null().cast(pl.Int8).to_numpy()
            mask_b = df[col_b].is_null().cast(pl.Int8).to_numpy()

            if np.std(mask_a) > 0 and np.std(mask_b) > 0:
                corr = float(np.corrcoef(mask_a, mask_b)[0, 1])
                if not (math.isnan(corr) or math.isinf(corr)):
                    if abs(corr) >= 0.4:
                        has_high_correlation = True
                        correlated_pairs.append({
                            "column_a": col_a,
                            "column_b": col_b,
                            "correlation": round(corr, 3)
                        })

    if has_high_correlation:
        mechanism = "MAR (Missing at Random - Statistically Correlated)"
        desc = (
            f"Detected {len(correlated_pairs)} cross-feature missingness correlation(s) (|r| >= 0.4). "
            "Data omissions occur in conjunction with other features, suggesting systemic omission patterns (MAR)."
        )
    else:
        mechanism = "MCAR (Missing Completely at Random)"
        desc = (
            "Null indicators exhibit low cross-feature correlation (|r| < 0.4). "
            "Missingness appears homogeneously and independently distributed across records."
        )

    return MissingPatternAssessment(
        overall_null_rate=overall_null_pct,
        mechanism_hypothesis=mechanism,
        correlated_missing_pairs=correlated_pairs,
        description=desc
    )
