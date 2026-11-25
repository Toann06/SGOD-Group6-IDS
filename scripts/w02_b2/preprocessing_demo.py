#!/usr/bin/env python3
"""
SGOD-P1-W02-B2 — Phase 3C: Preprocessing Pipeline Demo
=======================================================
Implements the full preprocessing pipeline contract for the HCRL Car-Hacking
CAN Bus IDS dataset.

Schema W01-B2 (15 columns):
  timestamp, can_id, dlc, data_0..data_7,
  flag_raw, label, attack_type, source_file, source_line

Extended schema (after preprocessing):
  + label_provenance  : 'observed' | 'inferred'
  + segment_id        : int (assigned during segmentation)
  + payload_values    : list[int] length 8  (0 for masked bytes)
  + payload_mask      : list[int] length 8  (1=valid, 0=masked/padding)
  + can_id_int        : int (hex -> int conversion)
  + iat               : float | None (inter-arrival time, seconds)
  + iat_scaled        : float | None (after scaler.transform)
"""
from __future__ import annotations

import csv
import io
import json
import logging
import math
import pickle
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("preproc")
malformed_logger = logging.getLogger("preproc.malformed")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_SOURCES = {
    "DoS_dataset.csv": "dos",
    "Fuzzy_dataset.csv": "fuzzy",
    "gear_dataset.csv": "gear",
    "RPM_dataset.csv": "rpm",
}
NORMAL_SOURCE = "normal_run_data.txt"

HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")
BYTE_RE = re.compile(r"^[0-9A-Fa-f]{2}$")
NORMAL_RE = re.compile(
    r"^Timestamp:\s*([0-9]+(?:\.[0-9]+)?)\s+ID:\s*([0-9A-Fa-f]+)\s+(\S+)\s+DLC:\s*([0-9]+)\s*(.*?)\s*$"
)

SCHEMA_COLS = [
    "timestamp", "can_id", "dlc",
    "data_0", "data_1", "data_2", "data_3",
    "data_4", "data_5", "data_6", "data_7",
    "flag_raw", "label", "attack_type",
    "source_file", "source_line",
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class ParsedRow:
    """Normalized, validated representation of a single CAN frame."""
    timestamp: float                    # float64, seconds since epoch
    can_id: str                         # hex string, lowercase, e.g. "0316"
    can_id_int: int                     # integer representation
    dlc: int                            # 0-8
    data: List[Optional[str]]           # 8 elements; None where DLC < position
    flag_raw: Optional[str]             # 'R', 'T', or None
    label: int                          # 0 (normal) or 1 (attack)
    label_provenance: str               # 'observed' or 'inferred'
    attack_type: str                    # 'normal'|'dos'|'fuzzy'|'gear'|'rpm'
    source_file: str
    source_line: int
    # Derived
    payload_values: List[int] = field(default_factory=lambda: [0]*8)
    payload_mask: List[int] = field(default_factory=lambda: [0]*8)
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    # Set during segmentation
    segment_id: int = 0
    # Set during feature extraction
    iat: Optional[float] = None
    iat_scaled: Optional[float] = None


# ---------------------------------------------------------------------------
# STEP 1: PARSE
# ---------------------------------------------------------------------------

def parse_csv_row(row: list, source_file: str, source_line: int) -> dict:
    """
    Parse a raw CSV row (list of strings, no header) into a normalized dict.

    CSV format: timestamp, can_id, dlc, [DLC bytes...], flag
    - CAN ID: kept as hex string (lowercase)
    - DLC: int
    - Timestamp: float64
    - Data bytes: list[str|None], length 8 (None for indices >= DLC)
    - flag_raw: 'R' or 'T'
    - label, label_provenance, attack_type derived

    Returns dict with schema W01-B2 fields + label_provenance.
    Raises ValueError on structural errors.
    """
    if len(row) < 3:
        raise ValueError("too_few_fields: need at least timestamp/can_id/dlc")

    ts_text, can_id_text, dlc_text = row[0].strip(), row[1].strip(), row[2].strip()

    # Timestamp
    try:
        timestamp = float(ts_text)
    except ValueError:
        raise ValueError(f"invalid_timestamp: '{ts_text}'")
    if not math.isfinite(timestamp):
        raise ValueError(f"non_finite_timestamp: {timestamp}")

    # CAN ID
    can_id_text = can_id_text.lower()
    if not HEX_RE.match(can_id_text):
        raise ValueError(f"invalid_can_id: '{can_id_text}'")
    can_id_int = int(can_id_text, 16)

    # DLC
    try:
        dlc = int(dlc_text)
    except ValueError:
        raise ValueError(f"invalid_dlc: '{dlc_text}'")
    if not (0 <= dlc <= 8):
        raise ValueError(f"dlc_out_of_range: {dlc}")

    # Payload bytes
    expected_total_fields = 3 + dlc + 1  # ts + id + dlc + bytes + flag
    if len(row) < expected_total_fields:
        raise ValueError(
            f"wrong_field_count: DLC={dlc} expects {expected_total_fields} fields, got {len(row)}"
        )

    data_bytes: List[Optional[str]] = []
    for i in range(dlc):
        b = row[3 + i].strip()
        if not BYTE_RE.match(b):
            raise ValueError(f"invalid_byte_at_index_{i}: '{b}'")
        data_bytes.append(b.lower())
    # Pad with None for positions >= DLC
    while len(data_bytes) < 8:
        data_bytes.append(None)

    # Flag (last field after bytes)
    flag_raw = row[3 + dlc].strip() if len(row) > 3 + dlc else ""
    if flag_raw not in ("R", "T"):
        raise ValueError(f"invalid_flag: '{flag_raw}'")

    label, provenance = normalize_label(flag_raw, source_type="csv")
    attack_type = CSV_SOURCES.get(source_file, "unknown")
    if label == 0:
        attack_type = "normal"

    return {
        "timestamp": timestamp,
        "can_id": can_id_text,
        "can_id_int": can_id_int,
        "dlc": dlc,
        "data_0": data_bytes[0],
        "data_1": data_bytes[1],
        "data_2": data_bytes[2],
        "data_3": data_bytes[3],
        "data_4": data_bytes[4],
        "data_5": data_bytes[5],
        "data_6": data_bytes[6],
        "data_7": data_bytes[7],
        "flag_raw": flag_raw,
        "label": label,
        "label_provenance": provenance,
        "attack_type": attack_type,
        "source_file": source_file,
        "source_line": source_line,
    }


def parse_txt_row(line: str, source_line: int, source_file: str = NORMAL_SOURCE) -> dict:
    """
    Parse a line from normal_run_data.txt into a normalized dict.

    Format: "Timestamp: <ts> ID: <id> <extra> DLC: <n> <bytes...>"
    - label = 0 (normal), label_provenance = 'inferred'
    - flag_raw = None

    Returns dict with schema W01-B2 fields + label_provenance.
    Returns None for malformed/unrecognizable lines (logs the error but does NOT raise).
    Malformed lines are logged via malformed_logger for audit.
    """
    line = line.strip()
    if not line:
        malformed_logger.warning("line %d: empty_line", source_line)
        return None

    m = NORMAL_RE.match(line)
    if not m:
        malformed_logger.warning(
            "line %d: unrecognized_txt_format: '%s'", source_line, line[:80]
        )
        return None

    ts_text, can_id_text, _extra, dlc_text, bytes_text = m.groups()

    # Timestamp
    try:
        timestamp = float(ts_text)
    except ValueError:
        raise ValueError(f"invalid_timestamp: '{ts_text}'")

    # CAN ID
    can_id_text = can_id_text.lower()
    if not HEX_RE.match(can_id_text):
        raise ValueError(f"invalid_can_id: '{can_id_text}'")
    can_id_int = int(can_id_text, 16)

    # DLC
    try:
        dlc = int(dlc_text)
    except ValueError:
        raise ValueError(f"invalid_dlc: '{dlc_text}'")
    if not (0 <= dlc <= 8):
        raise ValueError(f"dlc_out_of_range: {dlc}")

    # Bytes
    byte_tokens = bytes_text.strip().split() if bytes_text.strip() else []
    if len(byte_tokens) != dlc:
        raise ValueError(
            f"byte_count_mismatch: DLC={dlc} but got {len(byte_tokens)} bytes"
        )

    data_bytes: List[Optional[str]] = []
    for i, b in enumerate(byte_tokens):
        if not BYTE_RE.match(b):
            raise ValueError(f"invalid_byte_at_index_{i}: '{b}'")
        data_bytes.append(b.lower())
    while len(data_bytes) < 8:
        data_bytes.append(None)

    label, provenance = normalize_label(None, source_type="txt")

    return {
        "timestamp": timestamp,
        "can_id": can_id_text,
        "can_id_int": can_id_int,
        "dlc": dlc,
        "data_0": data_bytes[0],
        "data_1": data_bytes[1],
        "data_2": data_bytes[2],
        "data_3": data_bytes[3],
        "data_4": data_bytes[4],
        "data_5": data_bytes[5],
        "data_6": data_bytes[6],
        "data_7": data_bytes[7],
        "flag_raw": None,
        "label": label,
        "label_provenance": provenance,
        "attack_type": "normal",
        "source_file": source_file,
        "source_line": source_line,
    }


# ---------------------------------------------------------------------------
# STEP 2: VALIDATE
# ---------------------------------------------------------------------------

def validate_row(row_dict: dict) -> Tuple[bool, str]:
    """
    Stateless validation of a parsed row dict.

    Checks:
    - Required keys present
    - timestamp: finite float
    - can_id: non-empty hex string
    - dlc: 0-8
    - data byte count consistent with DLC
    - Each present byte: 2-char hex string
    - flag_raw: 'R', 'T', or None
    - label: 0 or 1
    - label_provenance: 'observed' or 'inferred'

    Returns (True, '') if valid, (False, error_message) otherwise.
    """
    required = [
        "timestamp", "can_id", "dlc",
        "data_0", "data_1", "data_2", "data_3",
        "data_4", "data_5", "data_6", "data_7",
        "flag_raw", "label", "label_provenance",
        "attack_type", "source_file", "source_line",
    ]
    for k in required:
        if k not in row_dict:
            return False, f"missing_key:{k}"

    # Timestamp
    ts = row_dict["timestamp"]
    if not isinstance(ts, (int, float)) or not math.isfinite(float(ts)):
        return False, f"invalid_timestamp:{ts}"

    # CAN ID
    can_id = str(row_dict.get("can_id", ""))
    if not can_id or not HEX_RE.match(can_id):
        return False, f"invalid_can_id:{can_id!r}"

    # DLC
    dlc = row_dict["dlc"]
    if not isinstance(dlc, int) or not (0 <= dlc <= 8):
        return False, f"dlc_out_of_range:{dlc}"

    # Data bytes
    for i in range(8):
        col = f"data_{i}"
        val = row_dict.get(col)
        if i < dlc:
            if val is None:
                return False, f"missing_byte_data_{i}_for_dlc_{dlc}"
            # Accept: hex string ('ab'), int (171), float (171.0)
            if isinstance(val, (int, float)):
                iv = int(val)
                if not (0 <= iv <= 255):
                    return False, f"byte_out_of_range_{col}:{val!r}"
            elif isinstance(val, str):
                if not BYTE_RE.match(val):
                    return False, f"invalid_byte_{col}:{val!r}"
            else:
                return False, f"invalid_byte_{col}:{val!r}"
        else:
            if val is not None:
                return False, f"unexpected_byte_data_{i}_for_dlc_{dlc}"

    # Flag
    flag = row_dict.get("flag_raw")
    if flag not in ("R", "T", None, ""):
        return False, f"invalid_flag_raw:{flag!r}"

    # Label
    label = row_dict.get("label")
    if label not in (0, 1):
        return False, f"invalid_label:{label!r}"

    # Provenance
    prov = row_dict.get("label_provenance")
    if prov not in ("observed", "inferred"):
        return False, f"invalid_label_provenance:{prov!r}"

    return True, ""


# ---------------------------------------------------------------------------
# STEP 3: NORMALIZE LABEL
# ---------------------------------------------------------------------------

def normalize_label(
    flag_raw: Optional[str], source_type: str
) -> Tuple[int, str]:
    """
    Map raw flag + source type to (label_int, provenance_str).

    Rules:
      CSV source, flag='R' → (0, 'observed')
      CSV source, flag='T' → (1, 'observed')
      TXT source (no flag)  → (0, 'inferred')

    Parameters
    ----------
    flag_raw : str | None  — 'R', 'T', or None
    source_type : str      — 'csv' or 'txt'

    Returns
    -------
    (label_int, provenance_str)
    """
    if source_type == "txt" or flag_raw is None:
        return 0, "inferred"
    flag_upper = str(flag_raw).upper()
    if flag_upper == "R":
        return 0, "observed"
    if flag_upper == "T":
        return 1, "observed"
    raise ValueError(f"unrecognized_flag_raw: {flag_raw!r}")


# ---------------------------------------------------------------------------
# STEP 4: EXTRACT PAYLOAD (stateless)
# ---------------------------------------------------------------------------

def extract_payload(row_dict: dict) -> Tuple[List[int], List[int]]:
    """
    Extract payload byte values and validity mask based on DLC.

    For each of the 8 byte positions:
      - If position < DLC: byte is valid → value = int(hex_str, 16), mask = 1
      - If position >= DLC: padding     → value = 0, mask = 0

    IMPORTANT: byte '00' (genuine zero) vs padding zero are distinguished
    solely by the mask:
      - '00' with mask=1  → actual zero byte present in frame
      - 0   with mask=0  → padding, position not transmitted

    Parameters
    ----------
    row_dict : dict  — parsed row containing data_0..data_7 and dlc

    Returns
    -------
    (values, mask)  — each is a list of 8 ints
    """
    dlc = int(row_dict["dlc"])
    values: List[int] = []
    mask: List[int] = []

    for i in range(8):
        col = f"data_{i}"
        byte_str = row_dict.get(col)
        if i < dlc and byte_str is not None:
            # Support both: hex string ('ab'), int (171), or float (171.0)
            if isinstance(byte_str, (int, float)):
                byte_int = int(byte_str)
            elif isinstance(byte_str, str):
                # Hex string from parser ('ab') or decimal string ('171')
                try:
                    byte_int = int(byte_str, 16)
                except ValueError:
                    byte_int = int(float(byte_str))
            else:
                byte_int = int(byte_str)
            values.append(byte_int & 0xFF)  # clamp to [0, 255]
            mask.append(1)
        else:
            values.append(0)
            mask.append(0)

    return values, mask


# ---------------------------------------------------------------------------
# STEP 5: PREPROCESSING PIPELINE CLASS
# ---------------------------------------------------------------------------

class PreprocessingPipeline:
    """
    Full preprocessing pipeline for CAN Bus IDS.

    Transformation taxonomy
    -----------------------
    Stateless (no fit needed):
      - parse_csv_row / parse_txt_row
      - validate_row
      - normalize_label
      - extract_payload (hex→int, DLC mask)
      - can_id hex→int

    Train-fitted (fit on train only, then apply to val/test):
      - StandardScaler for inter-arrival time (IAT)
      - Any future MinMaxScaler for other continuous features

    Model-specific (applied separately per model):
      - CAN ID embedding lookup (embedding matrix size depends on vocab)
      - Sequence windowing (window size depends on model)

    Usage
    -----
    # Training phase
    pipeline = PreprocessingPipeline(random_seed=42)
    pipeline.fit(train_df)
    train_features = pipeline.transform(train_df)

    # Inference / val / test (same scaler, no refit)
    val_features = pipeline.transform(val_df)

    # Persistence
    pipeline.save("pipeline.pkl")
    loaded = PreprocessingPipeline.load("pipeline.pkl")
    """

    VERSION = "1.0.0"

    def __init__(self, random_seed: int = 42, gap_seconds: float = 1.0):
        """
        Parameters
        ----------
        random_seed : int
            Seed for any stochastic operations (e.g., random split fallback).
        gap_seconds : float
            Timestamp gap threshold (seconds) used to assign segment_id.
        """
        self.random_seed = random_seed
        self.gap_seconds = gap_seconds
        self._is_fitted = False

        # Train-fitted scalers (sklearn-compatible interface)
        self._iat_mean: Optional[float] = None
        self._iat_std: Optional[float] = None

        # Metadata written at fit time
        self.fit_metadata: dict = {}

    # ------------------------------------------------------------------
    # FIT (train only)
    # ------------------------------------------------------------------

    def fit(self, train_df: pd.DataFrame) -> "PreprocessingPipeline":
        """
        Fit train-fitted transformers on train_df ONLY.

        Must NOT be called on val/test data to prevent leakage.

        Fits:
          - IAT StandardScaler (mean, std) from train IAT values

        Parameters
        ----------
        train_df : pd.DataFrame
            Rows in schema W01-B2 format (already parsed, validated).
            Must contain 'timestamp' column (float64).

        Returns self for chaining.
        """
        logger.info("Fitting pipeline on %d training rows", len(train_df))

        # Compute IAT on training data only
        from scripts.w02_b2.segment_utils import segment_context
        if "split" in train_df and not train_df["split"].eq("train").all():
            raise ValueError("fit requires train rows only")
        _, _, valid_iat = segment_context(train_df, self.gap_seconds)
        iats = valid_iat.dropna().to_numpy()

        if len(iats) == 0:
            self._iat_mean = 0.0
            self._iat_std = 1.0
        else:
            self._iat_mean = float(np.mean(iats))
            self._iat_std = float(np.std(iats))
            if self._iat_std == 0.0:
                self._iat_std = 1.0  # guard against constant IAT

        self._is_fitted = True
        self.fit_metadata = {
            "version": self.VERSION,
            "random_seed": self.random_seed,
            "gap_seconds": self.gap_seconds,
            "train_rows": len(train_df),
            "iat_mean": self._iat_mean,
            "iat_std": self._iat_std,
            "iat_sample_count": int(len(iats)),
        }
        logger.info(
            "Fit complete: IAT mean=%.6f std=%.6f (n=%d)",
            self._iat_mean, self._iat_std, len(iats),
        )
        return self

    # ------------------------------------------------------------------
    # TRANSFORM
    # ------------------------------------------------------------------

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply stateless + train-fitted transformations to df.

        Applies:
          1. payload_values, payload_mask  (stateless)
          2. can_id_int                    (stateless)
          3. segment_id                    (stateless — gap detection)
          4. iat (inter-arrival time)      (stateless computation)
          5. iat_scaled                    (train-fitted scaler)

        Does NOT modify df in place. Returns a new DataFrame with
        all original columns PLUS derived feature columns.

        Parameters
        ----------
        df : pd.DataFrame — input rows (W01-B2 schema)

        Returns
        -------
        pd.DataFrame with added feature columns.
        """
        if not self._is_fitted:
            raise RuntimeError(
                "Pipeline must be fitted before transform. Call fit(train_df) first."
            )

        result = df.copy()

        # 1. Payload extraction (stateless)
        payload_vals = []
        payload_masks = []
        for _, row in result.iterrows():
            v, m = extract_payload(row.to_dict())
            payload_vals.append(v)
            payload_masks.append(m)

        for i in range(8):
            result[f"pv_{i}"] = [v[i] for v in payload_vals]
            result[f"pm_{i}"] = [m[i] for m in payload_masks]

        # 2. CAN ID int (stateless)
        if "can_id_int" not in result.columns:
            result["can_id_int"] = result["can_id"].apply(
                lambda x: int(str(x), 16) if HEX_RE.match(str(x)) else -1
            )

        # 3-4. Preserve observation order and reset at every boundary.
        from scripts.w02_b2.segment_utils import segment_context
        result["segment_id"], _, result["iat"] = segment_context(result, self.gap_seconds)

        # 5. IAT scaled (train-fitted)
        result["iat_scaled"] = result["iat"].apply(
            lambda x: (x - self._iat_mean) / self._iat_std
            if x is not None and not pd.isna(x)
            else None
        )

        return result

    # ------------------------------------------------------------------
    # SAVE / LOAD
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Serialize pipeline to disk for inference reuse.

        Uses pickle to store fitted scaler parameters and metadata.
        The pipeline must be fitted before saving.

        Parameters
        ----------
        path : str — destination file path (e.g., 'pipeline.pkl')
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save an unfitted pipeline.")
        payload = {
            "version": self.VERSION,
            "random_seed": self.random_seed,
            "gap_seconds": self.gap_seconds,
            "iat_mean": self._iat_mean,
            "iat_std": self._iat_std,
            "fit_metadata": self.fit_metadata,
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f, protocol=4)
        logger.info("Pipeline saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "PreprocessingPipeline":
        """
        Load a previously saved pipeline from disk.

        Parameters
        ----------
        path : str — path to saved pipeline .pkl file

        Returns
        -------
        PreprocessingPipeline (fitted)
        """
        with open(path, "rb") as f:
            payload = pickle.load(f)
        pipeline = cls(
            random_seed=payload["random_seed"],
            gap_seconds=payload["gap_seconds"],
        )
        pipeline._iat_mean = payload["iat_mean"]
        pipeline._iat_std = payload["iat_std"]
        pipeline.fit_metadata = payload.get("fit_metadata", {})
        pipeline._is_fitted = True
        logger.info("Pipeline loaded from %s (version=%s)", path, payload.get("version"))
        return pipeline

    def get_fit_metadata(self) -> dict:
        """Return a copy of fit-time metadata (for audit)."""
        return dict(self.fit_metadata)


# ---------------------------------------------------------------------------
# MALFORMED ROW LOGGING HELPER
# ---------------------------------------------------------------------------

def log_malformed(source_file: str, source_line: int, reason: str, raw: str) -> None:
    """
    Log a malformed row WITHOUT modifying or discarding it silently.

    Format: JSON-structured log entry for downstream audit.
    """
    entry = {
        "event": "malformed_row",
        "source_file": source_file,
        "source_line": source_line,
        "reason": reason,
        "raw_preview": raw[:200],
    }
    malformed_logger.warning("%s", json.dumps(entry))


# ---------------------------------------------------------------------------
# DEMO: 20-row synthetic fixture
# ---------------------------------------------------------------------------

def build_synthetic_fixture() -> Tuple[List[dict], List[str]]:
    """
    Build 20 synthetic rows that exercise all pipeline branches:
    - 8 normal CSV rows (flag='R'), DLC in {2, 5, 6, 8}
    - 8 attack CSV rows (flag='T'), DLC in {2, 5, 6, 8}
    - 2 TXT rows (inferred label)
    - 2 malformed rows (structural errors)

    Returns (valid_rows_as_dicts, malformed_raw_strings)
    """
    rng = np.random.default_rng(42)
    base_ts = 1_478_198_376.0

    csv_rows = []
    for i in range(16):
        dlc = [2, 5, 6, 8][i % 4]
        flag = "R" if i < 8 else "T"
        ts = base_ts + i * 0.1
        can_id = f"{(0x0100 + i * 7):04x}"
        data_bytes = [f"{rng.integers(0, 256):02x}" for _ in range(dlc)]
        row = [str(ts), can_id, str(dlc)] + data_bytes + [flag]
        src = "DoS_dataset.csv" if flag == "T" else "RPM_dataset.csv"
        try:
            parsed = parse_csv_row(row, src, i + 1)
            csv_rows.append(parsed)
        except ValueError as e:
            log_malformed(src, i + 1, str(e), ",".join(row))

    # 2 TXT rows
    txt_lines = [
        "Timestamp: 1479121434.850202 ID: 0350 000 DLC: 8 05 28 84 66 6d 00 00 a2",
        "Timestamp: 1479121434.850423 ID: 02c0 000 DLC: 2 14 00",
    ]
    txt_rows = []
    for i, line in enumerate(txt_lines, start=1):
        try:
            parsed = parse_txt_row(line, source_line=i)
            txt_rows.append(parsed)
        except ValueError as e:
            log_malformed(NORMAL_SOURCE, i, str(e), line)

    # 2 malformed rows (deliberately broken)
    malformed_raw = [
        "1479121434,ZZZZ,8,00,00,00,00,00,00,00,00,T",   # bad CAN ID
        "1479121434,0316,9,00,00,00,00,00,00,00,00,00,T", # DLC out of range
    ]

    return csv_rows + txt_rows, malformed_raw


def run_demo() -> None:
    """
    Run end-to-end demo with 20-row synthetic fixture.
    Prints: input rows → parsed → validated → features.
    """
    print("=" * 70)
    print("SGOD-P1-W02-B2 Preprocessing Pipeline Demo")
    print("=" * 70)

    # --- Build fixture ---
    print("\n[1] Building 20-row synthetic fixture...")
    valid_rows, malformed_raws = build_synthetic_fixture()
    print(f"    Valid rows: {len(valid_rows)}")
    print(f"    Malformed rows (intentional): {len(malformed_raws)}")

    # --- Demonstrate malformed logging ---
    print("\n[2] Malformed rows — will be LOGGED, not silently dropped:")
    for i, raw in enumerate(malformed_raws, start=100):
        # Attempt parse to trigger log
        parts = raw.split(",")
        try:
            parse_csv_row(parts, "DoS_dataset.csv", i)
        except ValueError as e:
            log_malformed("DoS_dataset.csv", i, str(e), raw)

    # --- Convert to DataFrame ---
    df = pd.DataFrame(valid_rows)
    # Ensure data_* columns are properly typed (None → NaN is fine in pandas)
    print(f"\n[3] Parsed DataFrame shape: {df.shape}")
    print(f"    Columns: {list(df.columns)}")
    print("\n    First 5 rows (key columns):")
    display_cols = ["timestamp", "can_id", "dlc", "flag_raw", "label",
                    "label_provenance", "attack_type", "source_file"]
    print(df[display_cols].head(5).to_string(index=False))

    # --- Validate ---
    print("\n[4] Validating rows...")
    validation_results = []
    for _, row in df.iterrows():
        is_valid, err = validate_row(row.to_dict())
        validation_results.append({"valid": is_valid, "error": err})

    n_valid = sum(1 for r in validation_results if r["valid"])
    n_invalid = len(validation_results) - n_valid
    print(f"    Valid: {n_valid}, Invalid: {n_invalid}")
    if n_invalid:
        for i, r in enumerate(validation_results):
            if not r["valid"]:
                print(f"    Row {i}: {r['error']}")

    # --- Payload extraction demo ---
    print("\n[5] Payload extraction (DLC-based mask):")
    for _, row in df.head(4).iterrows():
        vals, mask = extract_payload(row.to_dict())
        print(
            f"    CAN {row['can_id']} DLC={row['dlc']:d}  "
            f"values={vals}  mask={mask}"
        )

    # --- Label normalization demo ---
    print("\n[6] Label normalization:")
    for flag, src in [("R", "csv"), ("T", "csv"), (None, "txt")]:
        lbl, prov = normalize_label(flag, src)
        print(f"    flag_raw={flag!r:4s}  source={src!r:5s}  → label={lbl}, provenance={prov!r}")

    # --- Pipeline fit + transform ---
    print("\n[7] Pipeline fit (on first 14 rows as 'train') + transform all 18:")
    train_df = df.iloc[:14].copy()
    all_df = df.copy()

    pipeline = PreprocessingPipeline(random_seed=42, gap_seconds=10.0)
    pipeline.fit(train_df)
    transformed = pipeline.transform(all_df)

    print(f"    Transformed shape: {transformed.shape}")
    feature_cols = ["can_id_int", "dlc", "segment_id", "iat", "iat_scaled",
                    "pv_0", "pv_1", "pm_0", "pm_1"]
    print("\n    Feature columns sample (first 5 rows):")
    print(transformed[feature_cols].head(5).to_string(index=False))
    print(f"\n    Fit metadata: {json.dumps(pipeline.get_fit_metadata(), indent=2)}")

    # --- Save / Load round-trip ---
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pipeline.save(tmp_path)
        loaded = PreprocessingPipeline.load(tmp_path)
        reloaded_transformed = loaded.transform(all_df)
        # Verify iat_scaled identical
        close = np.allclose(
            transformed["iat_scaled"].fillna(0).values,
            reloaded_transformed["iat_scaled"].fillna(0).values,
        )
        print(f"\n[8] Save/Load round-trip: IAT scaled values match = {close}")
    finally:
        os.unlink(tmp_path)

    print("\n[9] Summary")
    print(f"    Pipeline steps: 11")
    print(f"    Stateless transforms: parse_hex, dlc_check, payload_mask, label_normalize, segment_id, iat_compute")
    print(f"    Train-fitted transforms: IAT StandardScaler (mean={pipeline._iat_mean:.6f}, std={pipeline._iat_std:.6f})")
    print(f"    Model-specific: CAN ID embedding, sequence windowing (not in this script)")
    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
