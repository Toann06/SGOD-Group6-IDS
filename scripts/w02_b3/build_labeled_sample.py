#!/usr/bin/env python3
"""Build a small, deterministic, provenance-preserving HCRL labeled sample."""
from __future__ import annotations
import argparse, csv, hashlib, json, random, re
from collections import Counter
from pathlib import Path

MANDATORY = ["timestamp","can_id","dlc",*[f"data_{i}" for i in range(8)],"flag_raw","label","attack_type","source_file","source_line"]
OPTIONAL = ["label_provenance", "segment_id"]
SHARED_START, SHARED_END = "1478200727.419470", "1478201209.058944"
ATTACKS = {"dos_dataset.csv":"dos", "fuzzy_dataset.csv":"fuzzy", "gear_dataset.csv":"gear", "rpm_dataset.csv":"rpm"}
NORMAL_RE = re.compile(r"^Timestamp:\s+(\S+)\s+ID:\s+([0-9A-Fa-f]+)\s+\S+\s+DLC:\s+(\d+)\s*(.*)$")

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def valid_hex(value, width=None):
    return bool(re.fullmatch(r"[0-9a-fA-F]+", value or "")) and (width is None or len(value) == width)

def base_record(ts, can_id, dlc, payload, flag, source, line, provenance):
    if not ts or not valid_hex(can_id) or not 0 <= dlc <= 8 or len(payload) != dlc or any(not valid_hex(x, 2) for x in payload):
        raise ValueError("invalid timestamp/CAN ID/DLC/payload")
    attack = ATTACKS.get(source.lower()) if flag == "T" else None
    if flag not in ("R", "T", None): raise ValueError("invalid flag")
    return dict(zip(MANDATORY + OPTIONAL, [ts, can_id.lower(), dlc, *[x.lower() for x in payload], *([""]*(8-dlc)), flag or "", 1 if flag == "T" else 0, attack or "normal", source, line, provenance, 0]))

def parse_file(path: Path):
    is_txt = path.suffix.lower() == ".txt"
    with path.open(encoding="utf-8", newline="") as f:
        for line_no, raw in enumerate(f, 1):
            try:
                if is_txt:
                    m = NORMAL_RE.match(raw.strip())
                    if not m: raise ValueError("invalid_normal_format")
                    ts, can_id, dlc, rest = m.groups(); payload = rest.split(); dlc = int(dlc)
                    yield base_record(ts, can_id, dlc, payload, None, path.name, line_no, "inferred_from_source")
                else:
                    fields = next(csv.reader([raw]))
                    if len(fields) < 5: raise ValueError("csv_too_few_fields")
                    ts, can_id, dlc = fields[:3]; dlc = int(dlc); payload, flag = fields[3:-1], fields[-1].upper()
                    yield base_record(ts, can_id, dlc, payload, flag, path.name, line_no, "observed_flag")
            except (ValueError, csv.Error):
                continue  # malformed source rows are deliberately skipped, never repaired

def is_shared_tail(row):
    return row["source_file"].lower() in ATTACKS and SHARED_START <= row["timestamp"] <= SHARED_END

def stratum(row):
    if row["label_provenance"] == "inferred_from_source": return "normal_inferred"
    return row["attack_type"] if row["label"] == 1 else "normal_observed"

def validate(row):
    if list(row) != MANDATORY + OPTIONAL: raise ValueError("schema mismatch")
    if row["label"] not in (0,1) or (row["label"] == 1) != (row["attack_type"] in {"dos","fuzzy","gear","rpm"}): raise ValueError("label mapping")
    if row["label_provenance"] not in {"observed_flag","inferred_from_source"}: raise ValueError("provenance")
    if row["label_provenance"] == "inferred_from_source" and (row["flag_raw"] or row["label"] != 0): raise ValueError("TXT provenance")
    if not valid_hex(row["can_id"]): raise ValueError("CAN ID")
    dlc = row["dlc"]
    for i in range(8):
        value = row[f"data_{i}"]
        if (i < dlc and not valid_hex(value,2)) or (i >= dlc and value): raise ValueError("payload")
    if is_shared_tail(row): raise ValueError("shared tail")

def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument("--data-dir", type=Path, required=True); p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42); p.add_argument("--per-stratum", type=int, default=3); p.add_argument("--checksums", type=Path)
    a = p.parse_args(argv); rng = random.Random(a.seed); wanted = ["normal_observed","normal_inferred","dos","fuzzy","gear","rpm"]
    reservoirs, seen, files = {x:[] for x in wanted}, Counter(), []
    for path in sorted(a.data_dir.iterdir()):
        if path.name.lower() not in ATTACKS and path.name != "normal_run_data.txt": continue
        files.append({"file":path.name,"sha256":sha256(path)})
        for row in parse_file(path):
            if is_shared_tail(row): continue
            key = stratum(row); seen[key] += 1; bucket = reservoirs[key]
            if len(bucket) < a.per_stratum: bucket.append(row)
            else:
                j = rng.randrange(seen[key])
                if j < a.per_stratum: bucket[j] = row
    missing = [x for x in wanted if not reservoirs[x]]
    if missing: raise SystemExit("missing required strata: " + ", ".join(missing))
    rows = [r for key in wanted for r in reservoirs[key]]
    for r in rows: validate(r)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    sample = a.output_dir / "labeled_sample.csv"
    with sample.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=MANDATORY+OPTIONAL); w.writeheader(); w.writerows(rows)
    manifest = {"artifact":"SGOD-P1-W02-B3 labeled sample","seed":a.seed,"per_stratum":a.per_stratum,"mandatory_b2_columns":MANDATORY,"optional_metadata":OPTIONAL,"shared_tail_policy":"exclude (PROPOSED; DEC-002 pending approval)","shared_tail_range":[SHARED_START,SHARED_END],"source_files":files,"rows":len(rows),"selected_by_stratum":dict(Counter(stratum(r) for r in rows)),"eligible_seen_by_stratum":dict(seen),"malformed_policy":"skip and log upstream; never repair","sample_sha256":sha256(sample)}
    (a.output_dir/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
if __name__ == "__main__": main()
