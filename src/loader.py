"""CSV loader and batch utilities for the SGOD CAN Dataset schema (B2 v1)."""
from pathlib import Path
from typing import Iterator
import pandas as pd

B2_REQUIRED_COLUMNS = [
    "timestamp", "can_id", "dlc",
    "data_0", "data_1", "data_2", "data_3",
    "data_4", "data_5", "data_6", "data_7",
    "flag_raw", "label", "attack_type", "source_file", "source_line",
]


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load a CSV with BOM support and return a DataFrame."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError("Input file must have .csv extension")
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        raise ValueError("Input CSV is empty")
    if df.columns.duplicated().any():
        duplicated = df.columns[df.columns.duplicated()].tolist()
        raise ValueError(f"Duplicate column names: {duplicated}")
    return df


def validate_b2_schema(df: pd.DataFrame, strict: bool = False) -> dict:
    """Validate B2 schema and return a report. strict=True raises if required columns are missing."""
    missing_columns = [c for c in B2_REQUIRED_COLUMNS if c not in df.columns]
    if strict and missing_columns:
        raise ValueError(f"Missing B2 schema columns: {missing_columns}")
    report = {"schema_match": not missing_columns,
              "missing_schema_columns": missing_columns,
              "rows": int(len(df)),
              "columns": int(len(df.columns))}
    if "dlc" in df.columns:
        dlc_numeric = pd.to_numeric(df["dlc"], errors="coerce")
        report["invalid_dlc_rows"] = int((dlc_numeric.isna() | (dlc_numeric < 0) | (dlc_numeric > 8)).sum())
    if "label" in df.columns:
        label_numeric = pd.to_numeric(df["label"], errors="coerce")
        report["invalid_label_rows"] = int((label_numeric.isna() | ~label_numeric.isin([0, 1])).sum())
        report["label_counts"] = {str(k): int(v) for k, v in label_numeric.value_counts(dropna=False).sort_index().items()}
    if "attack_type" in df.columns:
        report["attack_type_counts"] = {str(k): int(v) for k, v in df["attack_type"].value_counts(dropna=False).sort_index().items()}
    report["missing_values_total"] = int(df.isna().sum().sum())
    report["missing_values_by_column"] = {str(k): int(v) for k, v in df.isna().sum().items() if v > 0}
    return report


def summarize(df: pd.DataFrame) -> dict:
    """Build a general dataset summary plus B2 schema validation if applicable."""
    summary = {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": [str(c) for c in df.columns],
        "missing_values_total": int(df.isna().sum().sum()),
        "missing_values_by_column": {str(k): int(v) for k, v in df.isna().sum().items() if v > 0},
    }
    if set(B2_REQUIRED_COLUMNS).issubset(df.columns):
        summary["b2_validation"] = validate_b2_schema(df)
    return summary


def iter_batches(df: pd.DataFrame, batch_size: int) -> Iterator[pd.DataFrame]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    for start in range(0, len(df), batch_size):
        yield df.iloc[start:start + batch_size].copy()


def save_batches(df: pd.DataFrame, batch_size: int, output_dir: str | Path) -> int:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for count, batch in enumerate(iter_batches(df, batch_size), start=1):
        batch.to_csv(output_dir / f"batch_{count:04d}.csv", index=False, encoding="utf-8-sig")
    return count
