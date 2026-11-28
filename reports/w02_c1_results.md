# Kết quả P1-W2-C1 trên dữ liệu HCRL

Đã chạy `src/c1_cleaner.py` bằng Python 3.12.14 trên toàn bộ năm tệp trong `data/raw/`. CSV bàn giao tại `data/processed/w02_c1/frames.csv` có 17.558.346 khung CAN, 17 cột và dung lượng 1.746.815.541 byte. 16 cột theo schema B2 và cột cuối ghi nguồn gốc nhãn.

| Tệp | Dòng đầu vào | Hợp lệ | Bị loại | Nhãn 0 | Nhãn 1 |
|---|---:|---:|---:|---:|---:|
| DoS_dataset.csv | 3.665.771 | 3.665.771 | 0 | 3.078.250 | 587.521 |
| Fuzzy_dataset.csv | 3.838.860 | 3.838.860 | 0 | 3.347.013 | 491.847 |
| gear_dataset.csv | 4.443.142 | 4.443.142 | 0 | 3.845.890 | 597.252 |
| RPM_dataset.csv | 4.621.702 | 4.621.702 | 0 | 3.966.805 | 654.897 |
| normal_run_data.txt | 988.872 | 988.871 | 1 | 988.871 | 0 |
| **Tổng** | **17.558.347** | **17.558.346** | **1** | **15.226.829** | **2.331.517** |

Dòng vật lý 988.872 của `normal_run_data.txt` kết thúc sau `Timestamp: 1479121941.287013`, thiếu ID và DLC. Cleaner ghi nguyên dòng với mã `invalid_normal_format` trong `errors.csv`. Cả bốn CSV có số byte payload khớp DLC và cờ R/T hợp lệ ở cuối từng dòng. Các khung hợp lệ trong phần đuôi chung của bốn CSV vẫn giữ được tên tệp và vị trí ban đầu.

## Kết quả kiểm thử

| Phép kiểm | Kết quả quan sát |
|---|---|
| Unit test và kiểm thử với tệp nhỏ | 6/6 đạt. Bộ năm tệp nhỏ gồm 19 dòng, 7 hợp lệ và 12 bị loại. Đã kiểm tra cả bản ghi hợp lệ nằm sau dòng lỗi. |
| Toàn vẹn nguồn | SHA-256 khi đọc và khi kiểm tra lại khớp manifest B3 cho 5/5 tệp. |
| Số lượng | Đọc lại toàn bộ CSV đầu ra. Số nhãn 0/1 từng tệp, số dòng đầu vào, hợp lệ và bị loại khớp kết quả B1. |
| Nội dung bàn giao B3 | Tìm theo cặp `source_file`, `source_line`. 18/18 bản ghi khớp từng cột xuất ra, gồm timestamp, số 0 đầu trong CAN ID, payload, cờ, nhãn và nguồn gốc nhãn. |
| Nhật ký lỗi | Tên tệp, số dòng, nguyên nhân và nội dung dòng bị loại khớp bản ghi lỗi B1. |

Lệnh tái lập và mô tả các mã lỗi nằm trong [hướng dẫn C1](../docs/w02_c1_parser_cleaner.md). Thống kê máy đọc được nằm trong `data/processed/w02_c1/summary.json`.
