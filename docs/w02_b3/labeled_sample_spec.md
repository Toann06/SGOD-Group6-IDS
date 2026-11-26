# Labeled sample specification

The sample is a reproducible handoff, not a statistically representative training corpus. It contains at least one each of observed normal, inferred normal, and `dos`, `fuzzy`, `gear`, `rpm` attack rows; the default is three per stratum. Sampling is seeded reservoir sampling over eligible records, so memory use is bounded and source-line provenance survives.

## Schema compatibility

The mandatory B2 contract is exactly 16 columns: `timestamp, can_id, dlc, data_0..data_7, flag_raw, label, attack_type, source_file, source_line`. This output appends optional `label_provenance, segment_id` solely for compatibility with B1's proposed extension. B2 schema v2 is not approved.

`timestamp` remains a string. `can_id` and each present payload byte are lowercase hexadecimal strings; payload bytes are exactly two characters, therefore `00` remains `00`. For `i >= dlc`, `data_i` is empty. CSV `R -> 0/normal`, `T -> 1/{dos,fuzzy,gear,rpm}` according to source file. TXT rows are `0/normal`, empty `flag_raw`, and `inferred_from_source`; CSV rows use `observed_flag`.

Malformed source rows are skipped rather than repaired. The known final malformed normal TXT line is consequently absent. The shared tail timestamp range `1478200727.419470`–`1478201209.058944` is excluded under the **proposed/pending** DEC-002 policy. The manifest records hashes, seed, policy, eligible counts and selected counts.
