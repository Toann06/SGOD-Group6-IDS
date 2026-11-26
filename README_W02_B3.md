# SGOD-P1-W02-B3 — labeled sample and FL partition handoff

Status: **Ready for Review** (not Done; reviewer confirmation required).

This artifact delivers a small, reproducible labeled sample and a future FL partition plan for C2/C3. It reads the five HCRL raw files only at execution time; raw data, full normalized data, and any archive of them are not stored here.

## Inputs and run

Input must be the five checksum-verified files described in `docs/w02_b3/source_integrity.md`. Python 3.10+ and the standard library are sufficient.

```powershell
python .\tests\w02_b3\test_build_labeled_sample.py
python .\scripts\w02_b3\build_labeled_sample.py --data-dir <raw-data-dir> --output-dir .\outputs\w02_b3
```

The generator validates the 16 required B2 columns, DLC/payload consistency, label mapping and provenance, hexadecimal strings (including `00`), and excludes the known shared-tail range. It reservoir-samples with seed 42, records source line and SHA-256, and writes only a tiny CSV and manifest.

## Outputs

- `outputs/w02_b3/labeled_sample.csv`: 18-column compatibility sample (16 mandatory B2 columns plus two proposed metadata fields).
- `outputs/w02_b3/manifest.json`: reproducibility, source hashes, counts and policy.
- `docs/w02_b3/`: usage constraints, proposed FL plan and decisions requiring approval.

`label_provenance` and `segment_id` are optional compatibility metadata from B1; they are not asserted to be part of an approved B2 schema. The sample uses `shared_tail_policy=exclude` as a proposed safe default only.

## Limits / pending decisions

DEC-002 (tail), DEC-003 (binary vs multiclass), DEC-004 (FL clients), and DEC-008 (70/15/15) remain pending A2/A3/mentor approval. There is one vehicle, hence no natural FL clients. This package does not generate whole-dataset partitions or make source files official clients.
