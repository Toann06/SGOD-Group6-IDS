# Handoff to C2/C3

Receive `outputs/labeled_sample.csv` and `outputs/manifest.json` as a parser/integration fixture. Validate its SHA-256 against the manifest before use. C2 can use the first 16 columns as the B2-compatible contract; tolerate or explicitly retain the two trailing optional metadata columns. C3 can bind provenance to `source_file`, `source_line`, source-file checksum and sample checksum.

Do not cast `can_id` or payload columns through numeric CSV inference: `00` is meaningful and must stay a two-character string. Do not treat missing payload above DLC as zero payload. Do not equate inferred TXT normal labels with observed CSV flags in reporting. Do not use `flag_raw`, labels, attack type, source metadata or provenance as model features.

Do not assume binary classification, 70/15/15, excluded shared tail, or source-file-per-client is approved. Use the manifest policy only as an explicit B3 proposed fixture policy. For real-scale work, rerun B2-approved preprocessing and a future approved partition builder against checksum-verified raw inputs; do not train from this small sample.
