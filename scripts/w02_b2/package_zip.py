"""
Package SGOD-P1-W02-B2 delivery ZIP
"""
import zipfile
import os
from pathlib import Path

ROOT = Path(r"D:\SGOD\SGOD-B2")
ZIP_PATH = ROOT / "SGOD-P1-W02-B2.zip"

EXCLUDED_PATTERNS = {
    "__pycache__", ".venv", ".git", ".pytest_cache",
    "DoS_dataset.csv", "Fuzzy_dataset.csv", "gear_dataset.csv",
    "RPM_dataset.csv", "normal_run_data.txt", "normal_run_data.7z",
}

INCLUDE_ROOTS = [
    "README_W02_B2.md",
    "requirements_w02_b2.txt",
    "docs/w02_b2",
    "scripts/w02_b2",
    "tests/w02_b2",
    "outputs/w02_b2",
]

def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDED_PATTERNS:
            return True
        if part.endswith(".pyc"):
            return True
    return False

file_count = 0
with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for entry in INCLUDE_ROOTS:
        full_path = ROOT / entry
        if full_path.is_file():
            arcname = str(Path(entry))
            zf.write(full_path, arcname)
            file_count += 1
            print(f"  + {arcname}")
        elif full_path.is_dir():
            for fpath in sorted(full_path.rglob("*")):
                if fpath.is_file():
                    rel = fpath.relative_to(ROOT)
                    if not should_exclude(rel):
                        zf.write(fpath, str(rel))
                        file_count += 1
                        print(f"  + {rel}")

print(f"\n[DONE] ZIP created: {ZIP_PATH}")
print(f"[INFO] Total files included: {file_count}")
print(f"[INFO] ZIP size: {ZIP_PATH.stat().st_size:,} bytes")
