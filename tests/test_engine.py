import pytest
import polars as pl
from backend.models import AuditConfig
from backend.engine.ingestion import read_dataset_to_polars
from backend.engine.profiler import profile_dataset, infer_semantic_type
from backend.engine.anomaly import calculate_numeric_stats, calculate_outliers, assess_missingness_mechanism
from backend.engine.remediation import generate_remediation_plan

def test_ingestion_csv_delimiter():
    csv_bytes = b"id;name;value\n1;Alpha;10.5\n2;Beta;20.0\n3;Gamma;30.0"
    df, fmt = read_dataset_to_polars(csv_bytes, "test.csv")
    assert df.height == 3
    assert df.width == 3
    assert "Delimited" in fmt

def test_ingestion_latin1_encoding():
    latin1_bytes = "id,city\n1,München\n2,Zürich".encode("latin-1")
    df, fmt = read_dataset_to_polars(latin1_bytes, "cities.csv")
    assert df.height == 2
    assert "city" in df.columns

def test_profiler_and_distribution_metrics():
    data = {
        "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "reading": [10.0, 10.2, 10.1, 9.9, 10.0, 10.3, 10.1, 9.8, 10.2, 500.0],
        "category": ["A", "A", "B", "B", "A", "B", "A", "B", "A", None]
    }
    df = pl.DataFrame(data)
    config = AuditConfig(iqr_multiplier=1.5, zscore_threshold=3.0)
    report = profile_dataset(df, "sample.csv", 1024, "CSV", config=config)
    
    assert report.summary.row_count == 10
    assert report.summary.column_count == 3
    assert "id" in report.summary.candidate_primary_keys
    
    reading_col = next(c for c in report.columns if c.name == "reading")
    assert reading_col.numeric_stats is not None
    assert reading_col.numeric_stats.skewness is not None
    assert reading_col.numeric_stats.kurtosis is not None
    assert reading_col.outliers.iqr_outlier_count >= 1
    assert reading_col.outliers.robust_zscore_outlier_count >= 1

    # Check remediation script generation
    assert "pl.read_csv" in report.remediation.polars_code
    assert "SELECT" in report.remediation.sql_code
    assert len(report.remediation.summary_actions) > 0

def test_missingness_mechanism_assessment():
    # Co-occurring nulls should indicate MAR correlation
    data = {
        "col_a": [1.0, None, 3.0, None, 5.0, 6.0, None, 8.0, 9.0, 10.0],
        "col_b": [2.0, None, 4.0, None, 6.0, 7.0, None, 9.0, 10.0, 11.0],
        "col_c": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    }
    df = pl.DataFrame(data)
    assessment = assess_missingness_mechanism(df)
    assert "MAR" in assessment.mechanism_hypothesis or "MCAR" in assessment.mechanism_hypothesis
    assert assessment.overall_null_rate > 0
