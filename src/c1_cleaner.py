"""Stream HCRL raw frames into the SGOD B2/B3 handoff schema."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory


# Contract from B3 docs/w02_b3/labeled_sample_spec.md and the C2 loader.
CSV_ATTACK_TYPES = {
    "DoS_dataset.csv": "dos",
    "Fuzzy_dataset.csv": "fuzzy",
    "gear_dataset.csv": "gear",
    "RPM_dataset.csv": "rpm",
}
NORMAL_FILE = "normal_run_data.txt"
SOURCES = (*CSV_ATTACK_TYPES, NORMAL_FILE)
COLUMNS = (
    "timestamp", "can_id", "dlc", *(f"data_{i}" for i in range(8)),
    "flag_raw", "label", "attack_type", "source_file", "source_line",
    "label_provenance",
)
TIMESTAMP = re.compile(r"[0-9]+(?:\.[0-9]+)?")
CAN_ID = re.compile(r"[0-9a-fA-F]+")
DLC = re.compile(r"[0-9]+")
HEX_BYTES = {f"{i:02x}" for i in range(256)}
NORMAL_FRAME = re.compile(r"Timestamp:\s*(\S+)\s+ID:\s*(\S+)\s+\S+\s+DLC:\s*(\S+)(?:\s+(.*))?")


class RowError(ValueError):
    """One malformed physical line. The exception text is a stable reason code."""


def parse_frame(line: str, source: str, line_number: int) -> tuple:
    """Parse one line from a known source, preserving spelling of timestamps and IDs."""
    line = line.strip()
    if not line:
        raise RowError("empty_line")
    if source == NORMAL_FILE:
        match = NORMAL_FRAME.fullmatch(line)
        if not match:
            raise RowError("invalid_normal_format")
        timestamp, can_id, dlc_text, payload_text = match.groups()
        payload = (payload_text or "").lower().split()
        flag, attack, provenance = "", "normal", "inferred_from_source"
    else:
        try:
            fields = next(csv.reader([line], strict=True))
        except csv.Error as exc:
            raise RowError("invalid_csv") from exc
        if len(fields) < 4:
            raise RowError("missing_fields")
        timestamp, can_id, dlc_text = (field.strip() for field in fields[:3])
        payload = [field.strip().lower() for field in fields[3:-1]]
        flag = fields[-1].strip().upper()
        if flag not in {"R", "T"}:
            raise RowError("invalid_flag")
        attack = CSV_ATTACK_TYPES[source] if flag == "T" else "normal"
        provenance = "observed_flag"

    if not TIMESTAMP.fullmatch(timestamp) or not math.isfinite(float(timestamp)):
        raise RowError("invalid_timestamp")
    if not CAN_ID.fullmatch(can_id) or int(can_id, 16) > 0x1FFFFFFF:
        raise RowError("invalid_can_id")
    dlc_digits = dlc_text.lstrip("0") or "0"
    if not DLC.fullmatch(dlc_text) or len(dlc_digits) > 1 or dlc_digits > "8":
        raise RowError("invalid_dlc")
    dlc = int(dlc_digits)
    if len(payload) != dlc:
        raise RowError("payload_length_mismatch")
    if not all(byte in HEX_BYTES for byte in payload):
        raise RowError("invalid_payload_byte")
    return (
        timestamp, can_id.lower(), dlc, *payload, *([""] * (8 - dlc)),
        flag, int(flag == "T"), attack, source, line_number, provenance,
    )


def clean_source(path: Path, frames, rejects) -> dict:
    reasons, types = Counter(), Counter()
    digest = hashlib.sha256()
    line_number = 0
    with path.open("rb") as stream:
        for line_number, raw in enumerate(stream, 1):
            digest.update(raw)
            try:
                line = raw.decode("utf-8")
                if line_number == 1:
                    line = line.removeprefix("\ufeff")
                frame = parse_frame(line, path.name, line_number)
            except (UnicodeDecodeError, RowError) as exc:
                reason = "invalid_encoding" if isinstance(exc, UnicodeDecodeError) else str(exc)
                reasons[reason] += 1
                rejects.writerow((path.name, line_number, reason,
                                  raw.rstrip(b"\r\n").decode("utf-8", errors="backslashreplace")))
                continue
            frames.writerow(frame)
            types[frame[COLUMNS.index("attack_type")]] += 1
    return {
        "source_file": path.name, "sha256": digest.hexdigest(), "input": line_number,
        "valid": sum(types.values()), "invalid": sum(reasons.values()),
        "attack_types": dict(types), "error_reasons": dict(reasons),
    }


def clean(input_dir: Path, output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    if output_dir.is_relative_to(input_dir.resolve()):
        raise ValueError("Output must be outside the raw input directory")
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}. Choose a new run directory.")
    sources = [input_dir / name for name in SOURCES]
    for path in sources:
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".c1-") as staging:
        run = Path(staging) / "run"
        run.mkdir()
        files = []
        with (run / "frames.csv").open("w", encoding="utf-8", newline="") as out, (
            run / "errors.csv"
        ).open("w", encoding="utf-8", newline="") as err:
            frames, rejects = csv.writer(out), csv.writer(err)
            frames.writerow(COLUMNS)
            rejects.writerow(("source_file", "source_line", "reason", "raw_line"))
            for path in sources:
                stats = clean_source(path, frames, rejects)
                files.append(stats)
                print(f"{path.name}: {stats['valid']} valid, {stats['invalid']} invalid", flush=True)
        totals = {key: sum(item[key] for item in files) for key in ("input", "valid", "invalid")}
        reasons = Counter()
        for item in files:
            reasons.update(item["error_reasons"])
        report = {"files": files, "totals": totals, "error_reasons": dict(reasons)}
        (run / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        run.rename(output_dir)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/w02_c1"))
    args = parser.parse_args()
    try:
        report = clean(args.input_dir, args.output_dir)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(json.dumps(report["totals"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
