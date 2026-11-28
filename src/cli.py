"""Command-line interface for C2 CAN DataLoader."""
import argparse
import json
from pathlib import Path

from loader import load_csv, summarize, validate_b2_schema, iter_batches, save_batches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SGOD C2 CAN DataLoader - CSV load, validation and batching")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows per batch (default: 1000)")
    parser.add_argument("--label", default="label", help="Label column name (default: label)")
    parser.add_argument("--save-batches", action="store_true", help="Export each batch as CSV")
    parser.add_argument("--output-dir", default="output", help="Output folder (default: output)")
    parser.add_argument("--strict-b2", action="store_true", help="Require all columns in B2 schema v1")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.batch_size <= 0:
        raise SystemExit("Error: --batch-size must be greater than 0")
    df = load_csv(args.input)
    if args.label and args.label not in df.columns:
        raise SystemExit(f"Error: label column '{args.label}' not found. Available: {list(df.columns)}")

    b2_report = validate_b2_schema(df, strict=args.strict_b2)
    print("=== Dataset Summary ===")
    print(json.dumps(summarize(df), indent=2, ensure_ascii=False))
    print("\n=== B2 Schema Check ===")
    print(json.dumps(b2_report, indent=2, ensure_ascii=False))

    total_batches = 0
    for total_batches, batch in enumerate(iter_batches(df, args.batch_size), start=1):
        print(f"Batch {total_batches}: {len(batch)} rows")
    print(f"Total batches: {total_batches}")

    if args.save_batches:
        output_dir = Path(args.output_dir)
        saved = save_batches(df, args.batch_size, output_dir)
        print(f"Saved {saved} batches to: {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
