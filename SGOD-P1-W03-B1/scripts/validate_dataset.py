#!/usr/bin/env python3
"""SGOD-P1-W03-B1 | validate_dataset.py  (v1.0)

Kiem tra doc lap du lieu tho HCRL Car-Hacking: toan ven (SHA-256), cau truc,
nhan, ty le lop, DLC, CAN ID, timestamp, doan duoi dung chung, ty le lop theo
split thoi gian. KHONG sua du lieu; chi doc va bao cao.

Parser viet lai doc lap voi can_parser.py cua W02-B1 de co the doi chieu cheo.

Cach chay:
    python validate_dataset.py --data-dir <thu muc raw> --out-dir <thu muc ket qua>
Yeu cau: Python 3.10+, pandas, numpy. Ket qua tat dinh (khong dung random).
Ma thoat: 0 = khong co loi nghiem trong; 1 = co it nhat mot kiem tra FAIL.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_VERSION = "1.0"
CSV_FILES = {
    "DoS_dataset.csv": "dos",
    "Fuzzy_dataset.csv": "fuzzy",
    "gear_dataset.csv": "gear",
    "RPM_dataset.csv": "rpm",
}
NORMAL_FILE = "normal_run_data.txt"
EXPECTED_SHA256 = {  # theo SHA256SUMS.txt cua B1 (15/11/2026) va data_specification_v0.2
    "DoS_dataset.csv": "09bf3136647b1d846d13c374f26208f06ffeba18369093fc57c8076fc56b795e",
    "Fuzzy_dataset.csv": "a0e78dff6365a1ad3d314973f1ac5879b57f9b80c40eb07b1e3bbe4aeddaecfe",
    "gear_dataset.csv": "b4eba43605fff337117ff30e13c33f63b56eec3b00927c8bccb31192df3bee23",
    "RPM_dataset.csv": "6718c6cb0a5fe6bdf0e966a680f1d6d7d79c063d603254d6118c16aaeb74974d",
    "normal_run_data.txt": "efbbafbf8e965c0d2f75eb97f1d118d0ae1c4b9f3077a6c4c000a26eb5be97ea",
}
TAIL_LINES = 891_068  # do W02-B1 (analyze_tail_overlap.py)
TAIL_TS_START, TAIL_TS_END = 1478200727.419470, 1478201209.058944
HEX_ID = r"[0-9A-Fa-f]+"
HEX_BYTE = r"[0-9A-Fa-f]{2}"
NORMAL_RE = re.compile(
    r"^Timestamp:\s*([0-9]+(?:\.[0-9]+)?)\s+ID:\s*([0-9A-Fa-f]+)\s+(\S+)\s+DLC:\s*([0-9]+)\s*(.*?)\s*$"
)
MAX_EXAMPLES = 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def tail_hash(path: Path, n: int) -> str:
    dq: collections.deque[bytes] = collections.deque(maxlen=n)
    with path.open("rb") as f:
        for line in f:
            dq.append(line)
    h = hashlib.sha256()
    for line in dq:
        h.update(line)
    return h.hexdigest()


class FileStats:
    def __init__(self, name: str, kind: str):
        self.name = name
        self.kind = kind
        self.lines = 0
        self.valid = 0
        self.errors: collections.Counter = collections.Counter()
        self.error_examples: list[dict] = []
        self.label_counts: collections.Counter = collections.Counter()  # label -> n
        self.dlc_label: collections.Counter = collections.Counter()  # (dlc,label) -> n
        self.id_label: collections.Counter = collections.Counter()  # (can_id,label) -> n
        self.id_len: collections.Counter = collections.Counter()
        self.max_id_int = -1
        self.ts_backwards = 0
        self.ts_equal = 0
        self.gaps: list[tuple[int, float]] = []  # (line sau gap, do dai gap)
        self.extra_field: collections.Counter = collections.Counter()
        self.ts_min = None
        self.ts_max = None
        self.ts_arrays: list[np.ndarray] = []
        self.label_arrays: list[np.ndarray] = []

    def add_error(self, reason: str, line_no: int, content: str):
        self.errors[reason] += 1
        if len(self.error_examples) < MAX_EXAMPLES:
            self.error_examples.append({"file": self.name, "line": line_no, "reason": reason, "content": content[:200]})


def track_timestamps(st: FileStats, ts: np.ndarray, line_nos: np.ndarray, state: dict, gap_seconds: float):
    """ts va line_nos: chi gom dong hop le, theo thu tu file."""
    if ts.size == 0:
        return
    prev = state.get("prev_ts")
    full = ts if prev is None else np.concatenate([[prev], ts])
    d = np.diff(full)
    lines = line_nos if prev is None else line_nos
    if prev is None:
        d_lines = line_nos[1:]
    else:
        d_lines = line_nos
    st.ts_backwards += int((d < 0).sum())
    st.ts_equal += int((d == 0).sum())
    big = np.where(d > gap_seconds)[0]
    for i in big:
        st.gaps.append((int(d_lines[i]), float(d[i])))
    state["prev_ts"] = float(ts[-1])
    st.ts_min = float(ts[0]) if st.ts_min is None else min(st.ts_min, float(ts[0]))
    st.ts_max = float(ts[-1]) if st.ts_max is None else max(st.ts_max, float(ts[-1]))


def process_csv(path: Path, attack_type: str, chunk: int, gap_seconds: float) -> FileStats:
    st = FileStats(path.name, "csv")
    state: dict = {}
    reader = pd.read_csv(
        path, header=None, names=list(range(16)), dtype=str, chunksize=chunk,
        engine="c", keep_default_na=False, na_values=[""], skip_blank_lines=False,
    )
    row0 = 0
    for df in reader:
        n = len(df)
        line_nos = np.arange(row0 + 1, row0 + 1 + n)
        row0 += n
        st.lines += n
        ts = pd.to_numeric(df[0], errors="coerce")
        dlc_f = pd.to_numeric(df[2], errors="coerce")
        dlc_ok = dlc_f.between(0, 8) & (dlc_f == np.floor(dlc_f))
        can_ok = df[1].str.fullmatch(HEX_ID).fillna(False).astype(bool)
        nfields = df.notna().sum(axis=1)
        dlc_i = dlc_f.fillna(0).astype(int).clip(0, 8)
        cnt_ok = nfields == (4 + dlc_i)
        arr = df.to_numpy(dtype=object)
        flag = arr[np.arange(n), (3 + dlc_i.to_numpy())]
        flag_ok = pd.Series(flag).isin(["R", "T"]).to_numpy()
        bad_payload = np.zeros(n, dtype=bool)
        for j in range(8):
            need = (dlc_i > j).to_numpy()
            ok_j = df[3 + j].str.fullmatch(HEX_BYTE).fillna(False).astype(bool).to_numpy()
            bad_payload |= need & ~ok_j
        ts_ok = ts.notna() & np.isfinite(ts.fillna(np.nan)) & (ts >= 0)

        reason = np.full(n, "", dtype=object)
        # thu tu uu tien: dong cuoi cung gan thang thang se bi ghi de -> dat tu nhe den nang
        reason[~flag_ok] = "invalid_flag"
        reason[bad_payload] = "invalid_payload_byte"
        reason[~cnt_ok.to_numpy()] = "field_count_not_equal_4_plus_dlc"
        reason[~can_ok.to_numpy()] = "invalid_can_id"
        reason[~dlc_ok.to_numpy()] = "invalid_or_out_of_range_dlc"
        reason[~ts_ok.to_numpy()] = "invalid_timestamp"
        reason[(nfields < 5).to_numpy()] = "too_few_fields"
        bad = reason != ""
        for i in np.where(bad)[0]:
            st.add_error(reason[i], int(line_nos[i]), ",".join("" if pd.isna(x) else str(x) for x in arr[i]).rstrip(","))
        good = ~bad
        st.valid += int(good.sum())
        if not good.any():
            continue
        g_flag = flag[good]
        g_label = (g_flag == "T").astype(np.uint8)
        g_dlc = dlc_i.to_numpy()[good]
        g_id = df.loc[good, 1].str.lower().to_numpy()
        g_ts = ts.to_numpy()[good].astype(np.float64)
        for lab, c in zip(*np.unique(g_label, return_counts=True)):
            st.label_counts[int(lab)] += int(c)
        for (d, lab), c in pd.Series(list(zip(g_dlc, g_label))).value_counts().items():
            st.dlc_label[(int(d), int(lab))] += int(c)
        vc = pd.DataFrame({"i": g_id, "l": g_label}).value_counts()
        for (cid, lab), c in vc.items():
            st.id_label[(cid, int(lab))] += int(c)
        for cid in set(g_id):
            st.id_len[len(cid)] += 0
            st.max_id_int = max(st.max_id_int, int(cid, 16))
        track_timestamps(st, g_ts, line_nos[good], state, gap_seconds)
        st.ts_arrays.append(g_ts)
        st.label_arrays.append(g_label)
    # do dai chuoi can_id (tren cac gia tri duy nhat)
    for (cid, _lab) in st.id_label:
        st.id_len[len(cid)] += 1
    return st


def process_normal(path: Path, gap_seconds: float) -> FileStats:
    st = FileStats(path.name, "txt")
    state: dict = {}
    ts_buf, ln_buf = [], []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            st.lines += 1
            m = NORMAL_RE.fullmatch(line.strip())
            if not m:
                st.add_error("invalid_normal_format", line_no, line)
                continue
            ts_t, cid, extra, dlc_t, payload = m.groups()
            dlc = int(dlc_t)
            data = payload.split()
            if not 0 <= dlc <= 8:
                st.add_error("dlc_out_of_range", line_no, line)
                continue
            if len(data) != dlc:
                st.add_error("payload_count_not_equal_dlc", line_no, line)
                continue
            if not all(re.fullmatch(HEX_BYTE, b) for b in data):
                st.add_error("invalid_payload_byte", line_no, line)
                continue
            st.valid += 1
            st.label_counts[0] += 1
            st.dlc_label[(dlc, 0)] += 1
            cid_l = cid.lower()
            st.id_label[(cid_l, 0)] += 1
            st.extra_field[extra] += 1
            st.max_id_int = max(st.max_id_int, int(cid_l, 16))
            ts_buf.append(float(ts_t))
            ln_buf.append(line_no)
    for (cid, _lab) in st.id_label:
        st.id_len[len(cid)] += 1
    ts = np.array(ts_buf, dtype=np.float64)
    track_timestamps(st, ts, np.array(ln_buf), state, gap_seconds)
    st.ts_arrays.append(ts)
    st.label_arrays.append(np.zeros(ts.size, dtype=np.uint8))
    return st


def split_ratio_table(stats: dict[str, FileStats]) -> pd.DataFrame:
    """Mo phong purged temporal split 70/15/15, purge 1% (A2 v1.2) theo tung file CSV,
    voi 2 che do doan duoi: exclude (mac dinh A2) va keep."""
    rows = []
    for name, st in stats.items():
        if st.kind != "csv":
            continue
        ts = np.concatenate(st.ts_arrays)
        lab = np.concatenate(st.label_arrays)
        in_tail = (ts >= TAIL_TS_START) & (ts <= TAIL_TS_END)
        for policy in ("exclude_tail", "keep_tail"):
            mask = ~in_tail if policy == "exclude_tail" else np.ones_like(in_tail)
            t, y = ts[mask], lab[mask]
            span = t.max() - t.min()
            gap = span * 0.01
            tv = t.min() + span * 0.70
            vt = t.min() + span * 0.85
            part = np.full(t.size, "purged", dtype=object)
            part[t < tv - gap / 2] = "train"
            part[(t >= tv + gap / 2) & (t <= vt - gap / 2)] = "val"
            part[t > vt + gap / 2] = "test"
            for p in ("train", "val", "test", "purged"):
                sel = part == p
                n = int(sel.sum())
                a = int(y[sel].sum())
                rows.append({
                    "file": name, "policy": policy, "split": p, "rows": n, "attack": a,
                    "normal": n - a, "attack_pct": round(100 * a / n, 2) if n else None,
                })
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--chunk", type=int, default=1_000_000)
    ap.add_argument("--gap-seconds", type=float, default=1.0)
    ap.add_argument("--skip-hash", action="store_true", help="bo qua SHA-256 (nhanh hon, khong khuyen nghi)")
    args = ap.parse_args()
    data_dir, out_dir = Path(args.data_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    def check(cid: str, desc: str, ok: bool, detail: str = ""):
        checks.append({"id": cid, "check": desc, "result": "PASS" if ok else "FAIL", "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {cid} {desc} {detail}")

    names = [*CSV_FILES, NORMAL_FILE]
    missing = [n for n in names if not (data_dir / n).exists()]
    check("V00", "Du 5 file nguon", not missing, f"thieu: {missing}" if missing else "")
    if missing:
        return 1

    # V01 toan ven
    hashes = {}
    if not args.skip_hash:
        for n in names:
            hashes[n] = sha256_file(data_dir / n)
            check("V01", f"SHA-256 {n}", hashes[n] == EXPECTED_SHA256[n], hashes[n][:16] + "...")

    stats: dict[str, FileStats] = {}
    for n, at in CSV_FILES.items():
        print(f"... doc {n}")
        stats[n] = process_csv(data_dir / n, at, args.chunk, args.gap_seconds)
    print(f"... doc {NORMAL_FILE}")
    stats[NORMAL_FILE] = process_normal(data_dir / NORMAL_FILE, args.gap_seconds)

    # ---- bang tong hop theo file
    rows = []
    for n, st in stats.items():
        a = st.label_counts.get(1, 0)
        z = st.label_counts.get(0, 0)
        rows.append({
            "file": n, "lines_read": st.lines, "valid": st.valid, "invalid": sum(st.errors.values()),
            "normal_0": z, "attack_1": a, "attack_pct": round(100 * a / st.valid, 2) if st.valid and st.kind == "csv" else None,
            "unique_can_id": len({c for c, _ in st.id_label}), "max_can_id_int": st.max_id_int,
            "ts_backwards": st.ts_backwards, "ts_equal_adjacent": st.ts_equal, "gaps_gt_1s": len(st.gaps),
            "label_provenance": "observed_flag" if st.kind == "csv" else "inferred_from_source",
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(out_dir / "file_summary.csv", index=False)

    # ---- DLC theo nhan
    dl = pd.DataFrame(
        [{"file": n, "dlc": d, "label": l, "count": c} for n, st in stats.items() for (d, l), c in sorted(st.dlc_label.items())]
    )
    dl.to_csv(out_dir / "dlc_by_label.csv", index=False)

    # ---- CAN ID theo nhan (top 30 / file) + ID chi xuat hien o attack
    idrows = []
    for n, st in stats.items():
        ids = collections.defaultdict(lambda: [0, 0])
        for (cid, lab), c in st.id_label.items():
            ids[cid][lab] += c
        for cid, (z, a) in sorted(ids.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:30]:
            idrows.append({"file": n, "can_id": cid, "normal": z, "attack": a})
    pd.DataFrame(idrows).to_csv(out_dir / "top_can_ids_by_label.csv", index=False)

    # ---- shortcut ID: ID nao tach lop hoan toan trong tung file CSV
    shortcut = []
    for n, st in stats.items():
        if st.kind != "csv":
            continue
        ids = collections.defaultdict(lambda: [0, 0])
        for (cid, lab), c in st.id_label.items():
            ids[cid][lab] += c
        pure_attack = {c: v for c, v in ids.items() if v[0] == 0 and v[1] > 0}
        mixed = {c: v for c, v in ids.items() if v[0] > 0 and v[1] > 0}
        att_total = st.label_counts.get(1, 0)
        cover = sum(v[1] for v in pure_attack.values())
        shortcut.append({
            "file": n, "ids_total": len(ids), "ids_attack_only": len(pure_attack),
            "attack_rows_in_attack_only_ids": cover,
            "pct_attack_covered_by_attack_only_ids": round(100 * cover / att_total, 2) if att_total else None,
            "ids_mixed": len(mixed),
            "top_attack_ids": ";".join(f"{c}:{v[1]}" for c, v in sorted(ids.items(), key=lambda kv: -kv[1][1])[:3]),
        })
    pd.DataFrame(shortcut).to_csv(out_dir / "can_id_shortcut_risk.csv", index=False)

    # ---- gap
    grows = [{"file": n, "line_after_gap": ln, "gap_seconds": round(g, 3)} for n, st in stats.items() for ln, g in st.gaps]
    pd.DataFrame(grows).to_csv(out_dir / "timestamp_gaps.csv", index=False)

    # ---- doan duoi dung chung
    tail = {}
    for n in CSV_FILES:
        st = stats[n]
        total_lines = st.lines
        tail[n] = {
            "tail_start_line_expected": total_lines - TAIL_LINES + 1,
            "gap_line_found": [ln for ln, _ in st.gaps],
            "tail_sha256": tail_hash(data_dir / n, TAIL_LINES),
        }
    tail_hashes = {v["tail_sha256"] for v in tail.values()}
    (out_dir / "shared_tail_check.json").write_text(json.dumps(tail, indent=2), encoding="utf-8")

    # ---- ty le lop theo split
    sp = split_ratio_table(stats)
    sp.to_csv(out_dir / "class_ratio_by_split.csv", index=False)

    # ---- loi
    errs = [e for st in stats.values() for e in st.error_examples]
    pd.DataFrame(errs, columns=["file", "line", "reason", "content"]).to_csv(out_dir / "errors_sample.csv", index=False)

    # ---- checks
    for n, st in stats.items():
        n_err = sum(st.errors.values())
        allowed = 1 if n == NORMAL_FILE else 0
        check("V02", f"Cau truc dong hop le {n}", n_err <= allowed, f"{n_err} dong loi {dict(st.errors)}")
    check("V03", "Nhan chi gom {0,1}", all(set(st.label_counts) <= {0, 1} for st in stats.values()))
    check("V04", "DLC trong 0..8 (tat ca ban ghi hop le)", all(d <= 8 for st in stats.values() for (d, _l) in st.dlc_label))
    dlc_set = sorted({d for st in stats.values() for (d, _l) in st.dlc_label})
    check("V05", "Tap DLC thuc te", True, str(dlc_set))
    check("V06", "CAN ID 11-bit (<= 0x7FF) o moi file", all(st.max_id_int <= 0x7FF for st in stats.values()),
          str({n: hex(st.max_id_int) for n, st in stats.items()}))
    check("V07", "Timestamp khong giam", all(st.ts_backwards == 0 for st in stats.values()),
          str({n: st.ts_backwards for n, st in stats.items() if st.ts_backwards}))
    check("V08", "Moi CSV co dung 1 gap > 1s", all(len(stats[n].gaps) == 1 for n in CSV_FILES),
          str({n: len(stats[n].gaps) for n in CSV_FILES}))
    check("V09", "Doan duoi 891.068 dong giong het o 4 CSV (hash)", len(tail_hashes) == 1, "so hash khac nhau: %d" % len(tail_hashes))
    tail_att = 0
    for n in CSV_FILES:
        ts = np.concatenate(stats[n].ts_arrays)
        lab = np.concatenate(stats[n].label_arrays)
        tail_att += int(lab[(ts >= TAIL_TS_START) & (ts <= TAIL_TS_END)].sum())
    check("V10", "Doan duoi khong chua attack (T)", tail_att == 0, f"so T trong doan duoi: {tail_att}")
    dos = stats["DoS_dataset.csv"]
    dos_a0 = dos.id_label.get(("0000", 1), 0)
    check("V11", "DoS: moi nhan T co CAN ID 0000", dos_a0 == dos.label_counts.get(1, 0), f"{dos_a0}/{dos.label_counts.get(1, 0)}")
    check("V12", "CAN ID giu chuoi hex co so 0 dan dau (do dai 4)", all(set(st.id_len) <= {4} for st in stats.values()),
          str({n: dict(st.id_len) for n, st in stats.items()}))

    out = {
        "script_version": SCRIPT_VERSION, "data_dir": str(data_dir), "sha256_actual": hashes,
        "checks": checks, "file_summary": summary.to_dict(orient="records"),
        "normal_txt_extra_field_values": dict(stats[NORMAL_FILE].extra_field),
    }
    (out_dir / "validation_summary.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    failed = [c for c in checks if c["result"] == "FAIL"]
    print(f"\nTONG: {len(checks) - len(failed)} PASS, {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
