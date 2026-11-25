"""
can_parser.py — SGOD-P1-W02-B2
================================
Robust CSV and TXT parser for HCRL Car-Hacking Dataset.

HCRL CSV Format (NO HEADER, 12 columns max):
  col 0  : timestamp (float, seconds since epoch)
  col 1  : can_id    (hex string, e.g. '0316')
  col 2  : dlc       (int, 0-8)
  col 3  : data_0    (hex byte string, e.g. 'ab')
  ...
  col 3+DLC-1 : data_{DLC-1}
  col 3+DLC   : flag  ('R' or 'T')
  col 3+DLC+1 : NaN  (if DLC < 8)
  ...
  col 11 : NaN  (if DLC < 8)

Key insight: flag is at column index 3+DLC, NOT at a fixed column.
When DLC=8, flag is at col 11 (index 3+8=11).
When DLC=5, flag is at col 8 (index 3+5=8), cols 9-11 are NaN.
When DLC=2, flag is at col 5 (index 3+2=5), cols 6-11 are NaN.

TXT Format (normal_run_data.txt):
  Timestamp: <ts>  ID: <id>  <extra>  DLC: <n>  <byte0> ... <byteN>

No NaN padding in TXT; bytes exactly match DLC count.

API
---
load_csv_chunk(path, start=0, chunksize=1000) -> Iterator[pd.DataFrame]
    Stream a CSV file in chunks without loading it all into RAM.

parse_csv_dataframe(df_raw) -> pd.DataFrame
    Convert a raw pd.read_csv(header=None) DataFrame to W01-B2 schema.

parse_txt_lines(lines, source_file='normal_run_data.txt', start_line=0) -> pd.DataFrame
    Parse a list of TXT lines to W01-B2 schema.

SCHEMA_COLS  : list of W01-B2 column names (15 columns)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterator, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
malformed_logger = logging.getLogger("can_parser.malformed")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA_COLS = [
    "timestamp", "can_id", "dlc",
    "data_0", "data_1", "data_2", "data_3",
    "data_4", "data_5", "data_6", "data_7",
    "flag_raw", "label", "attack_type",
    "source_file", "source_line",
]

BYTE_COLS = [f"data_{i}" for i in range(8)]

CSV_ATTACK_TYPES = {
    "DoS_dataset.csv":   "dos",
    "Fuzzy_dataset.csv": "fuzzy",
    "gear_dataset.csv":  "gear",
    "RPM_dataset.csv":   "rpm",
}

HEX_RE    = re.compile(r"^[0-9A-Fa-f]+$")
BYTE_HEX  = re.compile(r"^[0-9A-Fa-f]{1,2}$")  # 1 or 2 hex chars
NORMAL_RE = re.compile(
    r"Timestamp:\s*([0-9]+(?:\.[0-9]+)?)\s+"
    r"ID:\s*([0-9A-Fa-f]+)\s+\S+\s+"
    r"DLC:\s*([0-9]+)\s*(.*?)$"
)

# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _parse_flag_and_bytes(
    row_values: list,
    dlc: int,
) -> tuple[Optional[str], List[Optional[str]]]:
    """
    Extract flag and 8 data byte slots from a 12-element row value list.

    HCRL format: flag is at position (3 + dlc) in the row.
    Positions beyond flag are NaN (unused slots for smaller DLC frames).

    Parameters
    ----------
    row_values : list of 12 string/NaN values from the CSV row
    dlc        : number of valid payload bytes

    Returns
    -------
    (flag_raw, [data_0..data_7])
    flag_raw : 'R', 'T', or None if missing/malformed
    data_i   : hex string | None (None for positions >= dlc)
    """
    # Flag index in the row
    flag_idx = 3 + dlc
    if flag_idx < len(row_values):
        raw_flag = row_values[flag_idx]
        if pd.isna(raw_flag) if isinstance(raw_flag, float) else False:
            flag_raw: Optional[str] = None
        else:
            flag_raw = str(raw_flag).strip() if raw_flag is not None else None
            if flag_raw not in ("R", "T"):
                flag_raw = None
    else:
        flag_raw = None

    # Data bytes: positions 3 through 3+dlc-1 are valid payload
    data_bytes: List[Optional[str]] = []
    for i in range(8):
        col_pos = 3 + i
        if i < dlc:
            if col_pos < len(row_values):
                raw = row_values[col_pos]
                # Handle NaN (Python float nan)
                if isinstance(raw, float) and pd.isna(raw):
                    data_bytes.append(None)
                    continue
                s = str(raw).strip() if raw is not None else None
                if s is None:
                    data_bytes.append(None)
                    continue
                # Normalize to 2-char lowercase hex
                # Handle decimal strings like '68' or '68.0'
                try:
                    if "." in s:
                        # float representation like '68.0'
                        normalized = format(int(float(s)), "02x")
                    else:
                        # Try hex parse first (handles 'ab', '05', '68')
                        normalized = format(int(s, 16), "02x")
                except (ValueError, OverflowError):
                    data_bytes.append(None)
                    continue
                data_bytes.append(normalized)
            else:
                data_bytes.append(None)
        else:
            # Position outside DLC window → padding
            data_bytes.append(None)

    return flag_raw, data_bytes


def parse_csv_dataframe(
    df_raw: pd.DataFrame,
    source_file: str,
    start_line: int = 0,
) -> pd.DataFrame:
    """
    Convert a raw pd.read_csv(header=None) DataFrame to W01-B2 schema.

    Parameters
    ----------
    df_raw      : DataFrame from pd.read_csv(..., header=None)
    source_file : basename of the CSV file (e.g. 'DoS_dataset.csv')
    start_line  : line number of df_raw.index[0] in the original file (for audit)

    Returns
    -------
    pd.DataFrame with SCHEMA_COLS columns.
    Malformed rows are logged but excluded from the returned DataFrame.
    """
    attack_type_base = CSV_ATTACK_TYPES.get(source_file, "unknown")
    rows: list[dict] = []
    malformed_count = 0

    for rel_idx, raw_row in enumerate(df_raw.itertuples(index=False)):
        abs_line = start_line + rel_idx
        raw = list(raw_row)

        # --- timestamp ---
        try:
            ts = float(raw[0])
            if not (0 < ts < 2e9):  # sanity: Unix epoch range
                raise ValueError(f"timestamp out of range: {ts}")
        except (ValueError, TypeError, IndexError) as e:
            malformed_logger.warning("line %d: bad_timestamp: %s", abs_line, e)
            malformed_count += 1
            continue

        # --- can_id ---
        try:
            can_id_raw = str(raw[1]).strip().lower()
            if not HEX_RE.match(can_id_raw):
                raise ValueError(f"non-hex CAN ID: {can_id_raw!r}")
            can_id = can_id_raw
        except (ValueError, TypeError, IndexError) as e:
            malformed_logger.warning("line %d: bad_can_id: %s", abs_line, e)
            malformed_count += 1
            continue

        # --- dlc ---
        try:
            dlc = int(raw[2])
            if not (0 <= dlc <= 8):
                raise ValueError(f"DLC out of range: {dlc}")
        except (ValueError, TypeError, IndexError) as e:
            malformed_logger.warning("line %d: bad_dlc: %s", abs_line, e)
            malformed_count += 1
            continue

        # --- flag and bytes ---
        flag_raw, data_bytes = _parse_flag_and_bytes(raw, dlc)

        if flag_raw is None:
            malformed_logger.warning("line %d: missing/invalid flag", abs_line)
            malformed_count += 1
            continue

        label = 0 if flag_raw == "R" else 1
        attack_type = "normal" if label == 0 else attack_type_base

        rows.append({
            "timestamp":        ts,
            "can_id":           can_id,
            "dlc":              dlc,
            "data_0":           data_bytes[0],
            "data_1":           data_bytes[1],
            "data_2":           data_bytes[2],
            "data_3":           data_bytes[3],
            "data_4":           data_bytes[4],
            "data_5":           data_bytes[5],
            "data_6":           data_bytes[6],
            "data_7":           data_bytes[7],
            "flag_raw":         flag_raw,
            "label":            label,
            "label_provenance": "observed",
            "attack_type":      attack_type,
            "source_file":      source_file,
            "source_line":      abs_line,
        })

    if malformed_count:
        logger.warning(
            "parse_csv_dataframe[%s]: %d malformed row(s) in %d total",
            source_file, malformed_count, len(df_raw)
        )

    if not rows:
        return pd.DataFrame(columns=SCHEMA_COLS + ["label_provenance"])

    return pd.DataFrame(rows)


def load_csv_chunk(
    path: "str | Path",
    chunksize: int = 50_000,
    start_line: int = 0,
    skiprows: int = 0,
) -> "Iterator[pd.DataFrame]":
    """
    Stream a HCRL CSV file in chunks, yielding W01-B2 schema DataFrames.

    Parameters
    ----------
    path      : path to CSV file
    chunksize : rows per chunk
    start_line: starting line number for source_line tracking
    skiprows  : rows to skip from file beginning

    Yields
    ------
    pd.DataFrame with W01-B2 schema (parsed, validated, labeled)
    """
    path = Path(path)
    source_file = path.name
    current_line = start_line + skiprows

    # Strategy: read with explicit 12 column names.
    # HCRL CSV has variable columns (3+DLC+1 to 12) depending on DLC.
    # Using names=[0..11] forces pandas to always expect 12 cols;
    # rows with fewer cols get NaN-padded on the right (correct behaviour).
    COL_NAMES = list(range(12))

    for chunk_raw in pd.read_csv(
        path,
        header=None,
        names=COL_NAMES,
        skiprows=skiprows if skiprows > 0 else None,
        chunksize=chunksize,
        dtype=str,
        engine="c",
        on_bad_lines="warn",
    ):
        df_parsed = parse_csv_dataframe(chunk_raw, source_file, current_line)
        current_line += len(chunk_raw)
        if not df_parsed.empty:
            yield df_parsed


# ---------------------------------------------------------------------------
# TXT parsing
# ---------------------------------------------------------------------------

def parse_txt_lines(
    lines: "List[str] | Iterator[str]",
    source_file: str = "normal_run_data.txt",
    start_line: int = 0,
) -> pd.DataFrame:
    """
    Parse lines from normal_run_data.txt to W01-B2 schema.

    Returns
    -------
    pd.DataFrame — valid rows only. Malformed lines are logged and skipped.
    """
    rows: list[dict] = []
    malformed_count = 0

    for rel_idx, line in enumerate(lines):
        abs_line = start_line + rel_idx
        line = line.strip()
        if not line:
            continue

        m = NORMAL_RE.search(line)
        if not m:
            malformed_logger.warning(
                "line %d: unrecognized TXT format: %r", abs_line, line[:60]
            )
            malformed_count += 1
            continue

        ts_str, can_id_str, dlc_str, bytes_str = m.groups()

        try:
            ts = float(ts_str)
        except ValueError:
            malformed_logger.warning("line %d: bad_timestamp: %r", abs_line, ts_str)
            malformed_count += 1
            continue

        can_id = can_id_str.lower()
        if not HEX_RE.match(can_id):
            malformed_logger.warning("line %d: bad_can_id: %r", abs_line, can_id)
            malformed_count += 1
            continue

        try:
            dlc = int(dlc_str)
            if not (0 <= dlc <= 8):
                raise ValueError
        except ValueError:
            malformed_logger.warning("line %d: bad_dlc: %r", abs_line, dlc_str)
            malformed_count += 1
            continue

        byte_tokens = bytes_str.strip().split() if bytes_str.strip() else []
        # Allow ≤ DLC bytes (some lines may be truncated)
        data_bytes: List[Optional[str]] = []
        parse_ok = True
        for i in range(8):
            if i < dlc:
                if i < len(byte_tokens):
                    tok = byte_tokens[i].lower()
                    try:
                        normalized = format(int(tok, 16), "02x")
                    except ValueError:
                        malformed_logger.warning(
                            "line %d: bad_byte[%d]: %r", abs_line, i, tok
                        )
                        parse_ok = False
                        break
                    data_bytes.append(normalized)
                else:
                    malformed_logger.warning(
                        "line %d: missing_byte[%d] for DLC=%d", abs_line, i, dlc
                    )
                    parse_ok = False
                    break
            else:
                data_bytes.append(None)

        if not parse_ok:
            malformed_count += 1
            continue

        rows.append({
            "timestamp":        ts,
            "can_id":           can_id,
            "dlc":              dlc,
            "data_0":           data_bytes[0],
            "data_1":           data_bytes[1],
            "data_2":           data_bytes[2],
            "data_3":           data_bytes[3],
            "data_4":           data_bytes[4],
            "data_5":           data_bytes[5],
            "data_6":           data_bytes[6],
            "data_7":           data_bytes[7],
            "flag_raw":         None,
            "label":            0,
            "label_provenance": "inferred",
            "attack_type":      "normal",
            "source_file":      source_file,
            "source_line":      abs_line,
        })

    if malformed_count:
        logger.warning(
            "parse_txt_lines[%s]: %d malformed line(s)", source_file, malformed_count
        )

    if not rows:
        return pd.DataFrame(columns=SCHEMA_COLS + ["label_provenance"])

    return pd.DataFrame(rows)


def load_txt_chunk(
    path: "str | Path",
    chunksize: int = 50_000,
) -> "Iterator[pd.DataFrame]":
    """
    Stream normal_run_data.txt in chunks.

    Yields
    ------
    pd.DataFrame with W01-B2 schema
    """
    path = Path(path)
    source_file = path.name
    current_line = 0
    buffer: List[str] = []

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            buffer.append(line)
            if len(buffer) >= chunksize:
                df = parse_txt_lines(buffer, source_file, current_line)
                current_line += len(buffer)
                buffer = []
                if not df.empty:
                    yield df

    if buffer:
        df = parse_txt_lines(buffer, source_file, current_line)
        if not df.empty:
            yield df


# ---------------------------------------------------------------------------
# __main__ — smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    WORKSPACE = "D:/SGOD/SGOD-B2"
    total_ok = True

    for fname in ["DoS_dataset.csv", "Fuzzy_dataset.csv", "gear_dataset.csv", "RPM_dataset.csv"]:
        path = f"{WORKSPACE}/{fname}"
        chunks = list(load_csv_chunk(path, chunksize=1000))
        if not chunks:
            print(f"[FAIL] {fname}: no rows parsed")
            total_ok = False
            continue
        df = pd.concat(chunks, ignore_index=True)
        n = len(df)
        label_vc = df["label"].value_counts().to_dict()
        dlc_vc = df["dlc"].value_counts().to_dict()
        print(f"[OK] {fname}: {n} rows | labels={label_vc} | DLC={dlc_vc}")
        # Verify first row
        r0 = df.iloc[0]
        assert isinstance(r0["timestamp"], float), "timestamp must be float"
        assert isinstance(r0["can_id"], str), "can_id must be str"
        assert r0["label"] in (0, 1), "label must be 0 or 1"
        assert r0["label_provenance"] == "observed"

    # TXT
    chunks_txt = list(load_txt_chunk(f"{WORKSPACE}/normal_run_data.txt", chunksize=5000))
    if chunks_txt:
        df_txt = pd.concat(chunks_txt, ignore_index=True)
        print(f"[OK] normal_run_data.txt: {len(df_txt)} rows | "
              f"labels={df_txt['label'].value_counts().to_dict()} | "
              f"provenance={df_txt['label_provenance'].unique().tolist()}")
        assert (df_txt["label"] == 0).all(), "TXT must be all label=0"
        assert (df_txt["label_provenance"] == "inferred").all()
    else:
        print("[FAIL] normal_run_data.txt: no rows parsed")
        total_ok = False

    sys.exit(0 if total_ok else 1)
