import io
import csv
from typing import Tuple
import polars as pl
import pandas as pd

COMMON_ENCODINGS = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]

def decode_bytes_safely(sample_bytes: bytes) -> Tuple[str, str]:
    """Attempt decoding with multiple enterprise character encodings."""
    for enc in COMMON_ENCODINGS:
        try:
            return sample_bytes.decode(enc), enc
        except UnicodeDecodeError:
            continue
    # Fallback with replacement
    return sample_bytes.decode("utf-8", errors="replace"), "utf-8 (lossy)"

def detect_csv_delimiter(sample_bytes: bytes) -> str:
    """Detect delimiter from sample bytes using standard library csv.Sniffer."""
    try:
        sample_text, _ = decode_bytes_safely(sample_bytes[:32768])
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample_text, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except Exception:
        return ","

def read_dataset_to_polars(file_bytes: bytes, filename: str) -> Tuple[pl.DataFrame, str]:
    """
    Ingest CSV, TSV, JSON, or Parquet file buffer into high-performance Polars DataFrame
    with graceful handling of encoding variations, ragged lines, and malformed delimiters.
    """
    lower_name = filename.lower()
    
    # 1. Parquet
    if lower_name.endswith(".parquet") or lower_name.endswith(".pq"):
        try:
            df = pl.read_parquet(io.BytesIO(file_bytes))
            return df, "PARQUET"
        except Exception as e:
            raise ValueError(f"Failed to parse Parquet file: {str(e)}")

    # 2. JSON & NDJSON
    elif lower_name.endswith(".json") or lower_name.endswith(".ndjson"):
        try:
            df = pl.read_json(io.BytesIO(file_bytes))
            return df, "JSON"
        except Exception:
            try:
                df = pl.read_ndjson(io.BytesIO(file_bytes))
                return df, "NDJSON"
            except Exception:
                try:
                    pdf = pd.read_json(io.BytesIO(file_bytes))
                    df = pl.from_pandas(pdf)
                    return df, "JSON (normalized)"
                except Exception as je:
                    raise ValueError(f"Failed to parse JSON dataset: {str(je)}")

    # 3. CSV / TSV / Delimited
    else:
        delimiter = detect_csv_delimiter(file_bytes)
        # Try native Polars read with automatic error suppression
        try:
            df = pl.read_csv(
                io.BytesIO(file_bytes),
                separator=delimiter,
                ignore_errors=True,
                truncate_ragged_lines=True,
                infer_schema_length=20000
            )
            return df, f"Delimited (delimiter: '{delimiter}')"
        except Exception:
            # Multi-encoding fallback with pandas engine='python'
            last_err = None
            for enc in COMMON_ENCODINGS:
                try:
                    pdf = pd.read_csv(
                        io.BytesIO(file_bytes),
                        sep=delimiter,
                        encoding=enc,
                        on_bad_lines='skip',
                        low_memory=False
                    )
                    df = pl.from_pandas(pdf)
                    return df, f"Delimited (delimiter: '{delimiter}', encoding: '{enc}')"
                except Exception as err:
                    last_err = err
                    continue
            raise ValueError(f"Delimited ingestion failed across standard encodings: {str(last_err)}")
