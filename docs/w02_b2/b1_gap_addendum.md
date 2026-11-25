# B1 gap alignment — proposed revision

- Default gap threshold: >1 second, per B1 schema alignment; negative timestamp changes also reset history.
- Temporal features and preprocessing IAT reset at contiguous source, split, explicit segment or detected gap boundaries. First IAT is missing, frequency starts at 1. Fit uses only valid within-boundary IAT; explicitly non-train rows are rejected.
- Input must be in observation order. Inferred segment IDs are batch-local; for streaming production, persist segment IDs across chunks. Raw parser schema remains unchanged pending DEC-005. Explicit segment IDs are preserved in preprocessing.
- Baseline-A/B remain 23/22 features; neither includes segment_id or label_provenance. Baseline-B excludes raw CAN ID, not all ID-derived information.
- Shared-tail exclusion remains proposed (DEC-002). Run audit_b1_segments from workspace root to verify segment 0 equivalence on all four raw CSVs. Windows audit 24/11: PASS on all four CSVs (16,569,475 parsed rows; zero mismatches, zero tail attacks).
- Local extracted ZIP tests: 71 passed (66 existing + 5 regression tests). Windows rerun: 71 passed in 1.87s (saved log); multi-CSV sample audit and smoke test PASS.
- Reviewer decisions remain pending. This addendum supersedes conflicting gap descriptions in earlier specs for the proposed revision.
