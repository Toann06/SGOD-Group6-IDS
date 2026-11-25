# SGOD-P1-W02-B2 — Final review v1.1

Status: READY FOR REVIEW — chưa có reviewer sign-off.

- Windows: 71/71 PASS (1.87s, saved log); 5 regression tests B1.
- Full parsed CSV gap audit: 16.569.475 rows, 891.068 tail rows/file, zero segment0/non-tail mismatch and zero tail attacks.
- Sample leakage audit: 50.000 rows/CSV, all six cross-file pairs checked, PASS within sample. Scaler audit uses inter_arrival_time, not all features. TXT smoke: 100/100 valid.
- Default exclude, gap >1s, temporal boundaries source/split/segment; Baseline-A/B 23/22. Raw CAN ID shortcut risk remains; B still uses ID-derived features. Inferred segment IDs batch-local; streaming must preserve state. No model training claimed.
- Gear/RPM validation attack counts 683/547; full dataset leakage and coverage not verified. Payload repetition is not observation overlap.
- Pending DEC-002/005/007 and DEC-003/004/008/009; schema not formally approved. No reviewer confirmation or PR evidence in package.
- Reproduce from workspace root with installed dependencies (see outputs/w02_b2/installed_packages.txt), raw HCRL files in configured paths: python -m pytest tests/w02_b2 -v -rs; python -m scripts.w02_b2.audit_b1_segments; python -m scripts.w02_b2.audit_multi_csv_streaming; python -m scripts.w02_b2.smoke_test_real_data.
- This revision synchronizes documentation and summary only; raw evidence and Python code unchanged. Historical reports may retain older measurements explicitly as historical context.
