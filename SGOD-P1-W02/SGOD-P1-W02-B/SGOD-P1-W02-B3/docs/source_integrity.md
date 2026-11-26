# Source integrity reference

Raw data is deliberately neither copied nor archived in this artifact. Before a real run, compare SHA-256 with `SGOD-P1-W01-B/SGOD-B1-raw-data/SHA256SUMS.txt`:

| File | SHA-256 |
|---|---|
| DoS_dataset.csv | `09bf3136647b1d846d13c374f26208f06ffeba18369093fc57c8076fc56b795e` |
| Fuzzy_dataset.csv | `a0e78dff6365a1ad3d314973f1ac5879b57f9b80c40eb07b1e3bbe4aeddaecfe` |
| gear_dataset.csv | `b4eba43605fff337117ff30e13c33f63b56eec3b00927c8bccb31192df3bee23` |
| RPM_dataset.csv | `6718c6cb0a5fe6bdf0e966a680f1d6d7d79c063d603254d6118c16aaeb74974d` |
| normal_run_data.txt | `efbbafbf8e965c0d2f75eb97f1d118d0ae1c4b9f3077a6c4c000a26eb5be97ea` |

The generator recomputes hashes of input files and stores them in its manifest. It does not itself assert a hash matches the reference file; the operator must compare before use.
