# SGOD-P1-W03-B1 | Báo cáo kiểm tra chất lượng dữ liệu

Ngày chạy: 27/11/2026. Phạm vi: 5 file raw HCRL Car-Hacking (17.558.347 dòng). Reviewer dự kiến: B2. Từ điển dữ liệu đi kèm: `data_dictionary_v1.md`.

## 1. Kết luận ngắn

1. **Dữ liệu thô sạch về cấu trúc.** 17.558.346/17.558.347 dòng hợp lệ; 1 dòng lỗi duy nhất là dòng cuối bị cụt của `normal_run_data.txt`. Không có DLC ngoài 0..8, payload sai độ dài hay sai hex, flag lạ, timestamp giảm hoặc trùng, CAN ID ngoài 11-bit.
2. **Nhãn nhất quán**: chỉ có `R`/`T`, ánh xạ sang 0/1 đúng schema B2. Riêng 988.871 nhãn của normal TXT là nhãn *suy ra*.
3. **Số liệu độc lập khớp tuyệt đối** với W02-B1, B3 EDA v1 và C3 (bốn cài đặt khác nhau, cùng kết quả), và 6/6 SHA-256 khớp.
4. **Hai rủi ro lớn nằm ở cách dùng dữ liệu, không phải ở lỗi dữ liệu**: đoạn đuôi 891.068 dòng bị lặp ở 4 file (K1), và CAN ID gần như tự quyết định nhãn (K3).
5. **Phát hiện mới của B1-W03**: nếu giữ đoạn đuôi và chia theo thời gian (kiểu A2), tập test **không có một frame attack nào** và tập val rỗng ở 3/4 file; chỉ khi loại đoạn đuôi (mặc định hiện tại của A2) thì mới chia được đúng.
6. **Chưa làm được**: kiểm tra output sau pipeline (cần C1/C2) và đối chiếu quy tắc normalization/leakage với B2-W03. Cả hai chưa có tại thời điểm chạy.

## 2. Phương pháp

`scripts/validate_dataset.py` đọc raw theo khối 1 triệu dòng, parser viết lại **độc lập** với `can_parser.py` của W02. Không sửa dữ liệu, không dùng random. 21 kiểm tra, 6 test biên bằng `unittest` (flag lạ, thiếu byte, byte không hex, CAN ID không hex, DLC = 9, timestamp rác, timestamp đi lùi, normal TXT bị cụt, số byte ≠ DLC).

Chưa dùng bộ test biên có sẵn của C3, vì validator C3 làm việc trên bản ghi đã chuẩn hóa (`payload` dạng list). Có thể chạy cả hai và so kết quả ở bước nghiệm thu.

## 3. Kết quả 21 kiểm tra

| Mã | Kiểm tra | Kết quả |
|---|---|---|
| V00 | Đủ 5 file nguồn | PASS |
| V01 | SHA-256 5 file khớp `SHA256SUMS.txt` | PASS (5/5; thêm `.7z` khớp, tổng 6/6) |
| V02 | Cấu trúc dòng hợp lệ | PASS: CSV 0 lỗi; normal TXT 1 lỗi (dòng 988872) |
| V03 | Nhãn chỉ gồm {0, 1} | PASS |
| V04 | DLC trong 0..8 | PASS |
| V05 | Tập DLC thực tế | {2, 5, 6, 8} |
| V06 | CAN ID 11-bit (≤ 0x7FF) | PASS (max 0x690; Fuzzy 0x7FF) |
| V07 | Timestamp không giảm | PASS |
| V08 | Mỗi CSV có đúng 1 gap > 1 giây | PASS |
| V09 | Đoạn đuôi 891.068 dòng giống hệt ở 4 CSV | PASS (hash byte-level trùng: `262ef366…541fec`) |
| V10 | Đoạn đuôi không chứa `T` | PASS (0) |
| V11 | DoS: mọi `T` có CAN ID `0000` | PASS (587.521/587.521) |
| V12 | CAN ID giữ chuỗi hex có số 0 đầu | PASS (luôn 4 ký tự) |

Tổng: **21 PASS, 0 FAIL**. Log: `logs/validate_run_2026-11-27.log`.

Lưu ý: hash trong V09 khác hash đoạn đuôi ở `data_specification_v0.2` (`8dc026b6…`) vì W02 băm theo (timestamp, ID, DLC, data) còn V09 băm byte thô của dòng, gồm cả flag. Hai phép đo trả lời hai câu hỏi khác nhau; cả hai cho kết luận "giống hệt".

## 4. Đối chiếu chéo

| Chỉ tiêu | W02-B1 / B3 | C3 | B1-W03 (script này) |
|---|---|---|---|
| Dòng đọc | 17.558.347 | 17.558.347 | 17.558.347 |
| Hợp lệ | 17.558.346 | 17.558.346 | 17.558.346 |
| Attack / Normal | 2.331.517 / 15.226.829 | ngoài phạm vi C3 (chỉ đếm hợp lệ) | 2.331.517 / 15.226.829 |
| Dòng bắt đầu sau gap (DoS, Fuzzy, gear, RPM) | 2.774.704; 2.947.793; 3.552.075; 3.730.635 | ngoài phạm vi C3 | giống hệt |
| Độ dài gap (giây) | 22,36; 2.539,48; 5.588,13; 7.744,93 | ngoài phạm vi C3 | 22,358; 2.539,482; 5.588,126; 7.744,935 |
| DLC Fuzzy | {2: 34.382, 5: 53.451, 6: 3, 8: …} | ngoài phạm vi C3 | giống hệt |

## 5. Phát hiện chi tiết

### 5.1. Đoạn đuôi dùng chung (K1) và hệ quả lên split (K2)

Mọi frame attack nằm trước gap; 891.068 dòng sau gap là traffic bình thường và giống hệt nhau ở cả 4 CSV. Vì các gap rất dài (22 giây đến hơn 2 giờ), mốc cắt theo thời gian rơi vào *khoảng trống* giữa phần trước gap và đoạn đuôi:

| File | Giữ đoạn đuôi: train / val / test (số dòng) | % attack ở test |
|---|---|---:|
| DoS | 2.308.512 / 520.347 / 759.708 | 0,00 |
| Fuzzy | 2.947.792 / **0** / 891.068 | 0,00 |
| gear | 3.552.074 / **0** / 891.068 | 0,00 |
| RPM | 3.730.634 / **0** / 891.068 | 0,00 |

Khi loại đoạn đuôi, cả 3 split đều có 13 đến 22% attack (bảng 6.3 trong từ điển). Kết luận: quyết định D3 không chỉ là chuyện "trùng lặp" mà quyết định trực tiếp việc đánh giá có ý nghĩa hay không. **Đề xuất (chưa chốt):** ghi rõ trong báo cáo A3/A2 rằng `shared_tail_policy="keep"` kết hợp split thời gian là cấu hình không hợp lệ.

Giới hạn: đây là mô phỏng *công thức* của A2 trên timestamp thật, không phải chạy code A2.

### 5.2. CAN ID như một đường tắt (K3)

| File | Số ID | ID chỉ có ở attack | % frame attack nằm ở các ID đó | ID attack chính |
|---|---:|---:|---:|---|
| DoS | 27 | 1 | 100,0 | `0000` (587.521) |
| Fuzzy | 2.048 | 2.010 | 98,1 | ID ngẫu nhiên, mỗi ID ~290 frame |
| gear | 26 | 0 | 0,0 | `043f` (597.252 attack, 207.289 normal) |
| RPM | 26 | 0 | 0,0 | `0316` (654.897 attack, 216.334 normal) |

Với DoS và Fuzzy, mô hình chỉ nhìn `can_id` đã gần như tách được lớp. Điều này bình thường với loại tấn công đó nhưng sẽ làm accuracy cao giả tạo; cần ablation bỏ `can_id` (Baseline-B của B2/A2).

### 5.3. Điểm cần lưu ý khác

- **Normal TXT bị cụt dòng cuối**: dòng 988872 chỉ còn `Timestamp: 1479121941.287013`. Phát hiện ở cả W02, C3 và B1-W03.
- **Trường phụ `000`**: một giá trị duy nhất, không mang thông tin; không dùng làm feature.
- **Normal TXT thu cách các CSV khoảng 10,65 ngày** (W02 đo); khác phiên thu, nên không có ranh giới thời gian chung với các CSV.
- **Fuzzy** là file duy nhất có DLC 5 và 6 (đều là frame normal), nên DLC có thể rò thông tin ở file này; chưa đánh giá mức ảnh hưởng.

## 6. Việc chưa làm

| Việc | Lý do | Khi nào |
|---|---|---|
| Kiểm tra output sau pipeline (clean → encode → normalize → export) | C1/C2 chưa có | Sau khi C khóa pipeline (04/12) |
| Đối chiếu quy tắc normalization, leakage, version dataset với B2 | B2-W03 chưa xong | Giữa tuần, trao đổi trực tiếp |
| Kiểm phần trước gap của 4 CSV có trùng nhau không | Chưa ai kiểm (W02 mục 7) | Có thể làm tiếp, ước tính vài phút |
| Chạy kèm bộ test biên và validator của C3 trên cùng dữ liệu | Khác định dạng đầu vào | Khi nghiệm thu |
| Đối sánh `can_id`/`data` giữa các phiên (kiểm phân bố) | Ngoài phạm vi DoD | Tùy mentor |

## 7. Blocker và mock

- **Không dùng mock** trong báo cáo này: mọi số liệu lấy từ raw thật đã khớp SHA-256.
- **Blocker có kiểm soát**: chưa có output pipeline C1/C2 (chuẩn bị sẵn script, chạy lại khi có); chưa có kết quả B2-W03.
- **Không tự chốt**: D1, D3, D4, D5, D6 và phương án xử lý mất cân bằng đều giữ nguyên trạng thái chờ.

## 8. Chứng cứ

| Tệp | Nội dung |
|---|---|
| `scripts/validate_dataset.py` | Script kiểm tra |
| `tests/test_validate_dataset.py` | 6 test biên |
| `logs/validate_run_2026-11-27.log`, `logs/unittest_2026-11-27.log` | Log chạy |
| `results/validation_summary.json` | 21 kiểm tra + SHA-256 thực đo |
| `results/file_summary.csv` | Tổng hợp theo file |
| `results/dlc_by_label.csv`, `results/top_can_ids_by_label.csv`, `results/can_id_shortcut_risk.csv` | DLC, CAN ID, rủi ro đường tắt |
| `results/timestamp_gaps.csv`, `results/shared_tail_check.json` | Gap và đoạn đuôi |
| `results/class_ratio_by_split.csv` | Tỷ lệ lớp theo split mô phỏng |
| `results/errors_sample.csv` | Dòng lỗi |
