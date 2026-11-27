
import json
from datetime import datetime
from pathlib import Path


# Project root: SGOD-IDS/
ROOT_DIR = Path(__file__).resolve().parents[2]

LOG_DIR = ROOT_DIR / "results" / "logs"
LOG_FILE = LOG_DIR / "validation_errors.jsonl"


def log_error(dataset, record_number, record, errors):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "dataset": dataset,
        "record_number": record_number,
        "record": record,
        "errors": errors,
    }

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(entry, ensure_ascii=False) + "\n"
        )


def clear_log():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if LOG_FILE.exists():
        LOG_FILE.unlink()
