import io
import pytest
import polars as pl
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import AuditConfig
from backend.engine.profiler import profile_dataset, infer_semantic_type
from backend.engine.anomaly import calculate_numeric_stats, calculate_outliers, assess_missingness_mechanism
from backend.engine.remediation import generate_remediation_plan
from backend.engine.ingestion import read_dataset_to_polars

client = TestClient(app)

def test_single_column_dataframe():
    """Verify single-column dataset profiling without crashing or indexing errors."""
    data = {"metric": [1.0, 2.0, 3.0, 4.0, 5.0]}
    df = pl.DataFrame(data)
    report = profile_dataset(df, "single_col.csv", 128, "CSV")
    
    assert report.summary.column_count == 1
    assert report.summary.row_count == 5
    assert len(report.columns) == 1
    assert report.columns[0].name == "metric"
    assert "metric" in report.summary.candidate_primary_keys

def test_all_null_column():
    """Verify handling of 100% missing values in a column."""
    data = {
        "id": [1, 2, 3],
        "empty_feature": [None, None, None],
        "populated": ["a", "b", "c"]
    }
    df = pl.DataFrame(data)
    report = profile_dataset(df, "null_feature.csv", 256, "CSV")
    
    empty_col = next(c for c in report.columns if c.name == "empty_feature")
    assert empty_col.missing_percentage == 100.0
    assert empty_col.numeric_stats is None
    assert any("Severe missing rate" in issue for issue in empty_col.issues)

def test_mixed_type_inference():
    """Verify detection of string-encoded numerics and dates."""
    data = {
        "numeric_strings": ["12.5", "45.0", "-100.2", "0.0"],
        "date_strings": ["2026-01-01", "2026-02-15", "2026-03-30", "2026-04-10"],
        "mixed_strings": ["alpha", "123", "bravo", "true"]
    }
    df = pl.DataFrame(data)
    report = profile_dataset(df, "mixed_types.csv", 512, "CSV")
    
    num_str_col = next(c for c in report.columns if c.name == "numeric_strings")
    assert num_str_col.inferred_type == "Numeric (String-Encoded)"
    
    date_str_col = next(c for c in report.columns if c.name == "date_strings")
    assert date_str_col.inferred_type == "DateTime (String-Encoded)"

def test_extreme_statistical_outliers():
    """Verify detection of extreme values with IQR and robust MAD Z-scores."""
    # A distribution where 99 values are near 10, and 1 value is 1,000,000
    values = [10.0] * 50 + [10.5] * 49 + [1000000.0]
    df = pl.DataFrame({"values": values})
    
    config = AuditConfig(iqr_multiplier=1.5, zscore_threshold=3.0)
    report = profile_dataset(df, "extreme_outliers.csv", 1024, "CSV", config=config)
    
    val_col = report.columns[0]
    assert val_col.outliers is not None
    assert val_col.outliers.iqr_outlier_count >= 1
    assert val_col.outliers.robust_zscore_outlier_count >= 1
    assert val_col.numeric_stats.skewness is not None
    assert val_col.numeric_stats.skewness > 2.0

def test_empty_dataset_rejection():
    """Verify that uploading a 0-byte or header-only empty file returns a clean 400 error."""
    response = client.post(
        "/api/audit",
        files={"file": ("empty.csv", b"", "text/csv")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_all_constant_column():
    """Verify that constant columns (zero variance) are flagged."""
    data = {
        "id": [1, 2, 3, 4],
        "constant_col": ["FIXED", "FIXED", "FIXED", "FIXED"]
    }
    df = pl.DataFrame(data)
    report = profile_dataset(df, "constant.csv", 128, "CSV")
    
    const_col = next(c for c in report.columns if c.name == "constant_col")
    assert any("Constant column" in issue for issue in const_col.issues)
