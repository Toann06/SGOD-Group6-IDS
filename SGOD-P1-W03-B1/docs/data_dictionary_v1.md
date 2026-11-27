# SGOD-P1-W03-B1 | Data Dictionary v1.0 (HCRL Car-Hacking)

| Mục | Giá trị |
|---|---|
| Phiên bản | **v1.0-rc1**, 27/11/2026 |
| Trạng thái | Bản hoàn thiện để B2 review. Các mục ghi **[CHỜ]** phụ thuộc C1/C2, B2-W03 hoặc mentor, **chưa tự chốt** |
| Owner / Reviewer | B1 / B2 (dự kiến) |
| REQ | REQ-02 |
| Kế thừa | schema v1 (W01-B2), input contract + EDA v1 (W01-B3), data_specification v0.2 (W02-B1), A2 Handover v1.2, A3 v0.5, C3 validator |

Quy ước nhãn: **[ĐO]** đo trực tiếp trên dữ liệu thật ngày 27/11/2026 bằng `scripts/validate_dataset.py`; **[SUY RA]** tính từ số [ĐO]; **[ĐỀ XUẤT]** chưa ai chốt; **[CHỜ]** đang đợi bên khác.

---

## 1. Phiên bản dataset và toàn vẹn

Chỉ đúng với 5 file raw dưới đây. Raw **không** đưa vào repo (D1: license chưa được mentor xác nhận bằng văn bản).

| File | Định dạng | Kích thước (byte) | SHA-256 | Dòng đọc | Thời gian (epoch giây) |
|---|---|---:|---|---:|---|
| `DoS_dataset.csv` | CSV, không header | 190.058.708 | `09bf3136647b1d84…56b795e` | 3.665.771 | 1478198376,389 → 1478201209,059 |
| `Fuzzy_dataset.csv` | CSV, không header | 198.520.767 | `a0e78dff6365a1ad…eaecfe` | 3.838.860 | 1478195721,904 → 1478201209,059 |
| `gear_dataset.csv` | CSV, không header | 230.320.414 | `b4eba43605fff337…ee23` | 4.443.142 | 1478193190,057 → 1478201209,059 |
| `RPM_dataset.csv` | CSV, không header | 239.581.936 | `6718c6cb0a5fe6bd…74974d` | 4.621.702 | 1478191030,045 → 1478201209,059 |
| `normal_run_data.txt` | Log văn bản | 87.371.776 | `efbbafbf8e965c0d…be97ea` | 988.872 | 1479121434,850 → 1479121941,287 |

[ĐO] 6/6 hash (gồm cả `normal_run_data.7z` = `ea326338…ffa15`) khớp `SHA256SUMS.txt` của B1. SHA-256 đầy đủ nằm ở `results/validation_summary.json`.

---

## 2. Định dạng file nguồn

**4 file CSV** (không header, một dòng = một frame): `timestamp, can_id, dlc, <đúng dlc byte DATA>, flag`. Số trường mỗi dòng = 4 + DLC. Flag luôn ở **cuối dòng**, nên **không được** đọc cột 12 cố định (DLC < 8 làm flag lệch cột).

**`normal_run_data.txt`**: `Timestamp: <ts>  ID: <id>  <trường phụ>  DLC: <n>  <n byte hex cách nhau bằng khoảng trắng>`. Không có flag. [ĐO] trường phụ chỉ có một giá trị `000` ở 988.871/988.871 dòng hợp lệ; ý nghĩa chưa xác định, giữ lại nhưng không dùng làm feature.

---

## 3. Bảng dữ liệu chuẩn hóa (18 cột)

Đầu ra của `W02-B1/scripts/preprocess.py` (schema v1 của B2 có 16 cột, cộng 2 cột đề xuất của B1-W02).

> **Đính chính tài liệu:** `data_specification_v0.2` ghi "15 cột của B2 + 2 = 17". Đếm lại theo `schema_v1.md` và `COLUMNS` trong `preprocess.py`: B2 có **16** cột, tổng là **18**. A2 v1.0.0 đã ghi nhận cùng điều này. Đề nghị sửa ở bản v0.3.

| # | Cột | Kiểu | Miền giá trị | Null | Ý nghĩa và quy tắc | Được vào X? |
|---:|---|---|---|---|---|---|
| 1 | `timestamp` | string (số thập phân) | số hữu hạn ≥ 0, 6 chữ số thập phân | không | Thời điểm ghi frame. Giữ dạng chuỗi để so khớp chính xác. [ĐO] không giảm, không trùng liền kề ở cả 5 file | **Không** (A2 cấm) |
| 2 | `can_id` | string hex lowercase | `0000`…`07ff` | không | Mã arbitration ID, **giữ số 0 đầu**. [ĐO] luôn 4 ký tự, tối đa `0x7FF` (11-bit); max thật `0x690` ở normal/DoS/gear/RPM, `0x7FF` ở Fuzzy | Có, sau mã hóa (xem mục 5) |
| 3 | `dlc` | integer | 0..8; thực tế {2, 5, 6, 8} | không | Số byte DATA. Không giả định luôn 8 | Có |
| 4–11 | `data_0` … `data_7` | string hex 2 ký tự | `00`…`ff` | có, khi `i >= dlc` | Byte DATA thứ i+1. Null do DLC nhỏ hơn 8 **không phải lỗi** | Có, sau giải mã hex |
| 12 | `flag_raw` | string | `R`, `T` | có (normal TXT) | Nhãn gốc của HCRL. `R` = frame thường, `T` = frame bị chèn | **Không** (rò nhãn) |
| 13 | `label` | integer | 0, 1 | không | 0 = normal, 1 = attack (mục 4) | **Không** (đây là y) |
| 14 | `attack_type` | string | `normal`, `dos`, `fuzzy`, `gear`, `rpm` | không | Loại tấn công, suy ra từ tên file khi `flag=T` | **Không** (y đa lớp) |
| 15 | `source_file` | string | 5 tên file | không | Nguồn, để truy vết | **Không** |
| 16 | `source_line` | integer | ≥ 1 | không | Số dòng trong file nguồn | **Không** |
| 17 | `label_provenance` | string | `observed_flag`, `inferred_from_source` | không | Tách nhãn quan sát (4 CSV) khỏi nhãn suy ra (normal TXT). **[ĐỀ XUẤT D6]** | **Không** |
| 18 | `segment_id` | integer | ≥ 0 | không | Tăng 1 sau mỗi khoảng timestamp > 1 giây trong cùng file; chỉ đánh dấu, không cắt dữ liệu. **[ĐỀ XUẤT D6]** | **Không** (chỉ làm ranh giới) |

Ví dụ (từ `sample_10.csv`, đã đối chiếu 10/10 với raw ở W01-B2):

```
1478198377.185137,0000,8,00,00,00,00,00,00,00,00,T,1,dos,DoS_dataset.csv,1477
```

---

## 4. Từ điển nhãn

| Nguồn | Giá trị gốc | `label` | `attack_type` | `label_provenance` |
|---|---|---:|---|---|
| 4 file CSV | `R` | 0 | `normal` | `observed_flag` |
| `DoS_dataset.csv` | `T` | 1 | `dos` | `observed_flag` |
| `Fuzzy_dataset.csv` | `T` | 1 | `fuzzy` | `observed_flag` |
| `gear_dataset.csv` | `T` | 1 | `gear` | `observed_flag` |
| `RPM_dataset.csv` | `T` | 1 | `rpm` | `observed_flag` |
| `normal_run_data.txt` | không có | 0 | `normal` | `inferred_from_source` |

- Nhị phân: dùng `label`. Đa lớp (A2 `LabelMapper.for_hcrl`): `normal=0, dos=1, fuzzy=2, gear=3, rpm=4` (5 lớp).
- **Binary hay multiclass chưa chốt (D4, mentor)**; giữ cả hai cột.
- Nhãn của normal TXT (988.871 bản ghi) là **suy ra từ tên file**, phải báo cáo tách riêng khỏi nhãn quan sát.
- A3 v0.5 đang dùng mock 6 lớp; HCRL thật chỉ có 5 lớp (bao gồm normal). Cần A3 cập nhật khi nối dữ liệu thật.

---

## 5. Từ điển feature đưa vào mô hình (theo A2 Handover v1.2)

Thứ tự feature là hợp đồng giữa A2, B, C và mọi client FL. Trạng thái các profile do A2 quyết định, không phải B1.

| Profile (A2) | Số chiều | Thứ tự | Trạng thái |
|---|---:|---|---|
| `mock_10` (`0.1.0-mock`) | 10 | `can_id, dlc, data_0 … data_7` | MOCK |
| `hcrl_frame_18` (`1.0.0`) | 18 | `can_id_int, dlc, data_0 … data_7, payload_mask_0 … payload_mask_7` | PROPOSED |
| `b2_baseline_a_23` | 23 | 18 frame + 5 feature thời gian nhân quả | PENDING_APPROVAL |
| `b2_baseline_b_22` | 22 | 17 frame (bỏ `can_id_int`) + 5 thời gian | PENDING_APPROVAL |

Quy tắc mã hóa từ bảng dữ liệu chuẩn hóa sang tensor `X` (float32, shape `(B, d)`) và `y` (int64, shape `(B,)`):

| Trường | Quy tắc | Ghi chú / điểm chờ |
|---|---|---|
| `can_id` | hex → số nguyên (`int(x, 16)`), rồi chia miền cố định 2047 (HCRL chỉ có 11-bit) hoặc StandardScaler | **[CHỜ]** cách mã hóa ID (scale, embedding, tần suất) còn OPEN ở A2 |
| `dlc` | số nguyên, chia 8 nếu dùng miền cố định | |
| `data_i`, `i < dlc` | **hex** → 0..255, chia 255 nếu dùng miền cố định | Phải khai báo `payload_encoding="hex"`. Chuỗi `"10"` là 16, không phải 10; để `auto` có thể đoán sai |
| `data_i`, `i >= dlc` | 0.0, `payload_mask_i = 0` | Đây là padding, không phải dữ liệu thiếu |
| Byte thiếu trong `i < dlc` | từ chối bản ghi (mặc định A2 v1.2) | [ĐO] 0 bản ghi như vậy trong dữ liệu thật |
| Chuẩn hóa | fit **chỉ trên train**; trong FL cần phương án không rò thống kê giữa client | **[CHỜ]** A2/A1/C chốt (fixed-domain hay federated stats); B2-W03 giữ quy tắc normalization |

Không bao giờ đưa vào `X`: `timestamp, flag_raw, label, attack_type, source_file, source_line, label_provenance, segment_id`.

---

## 6. Tỷ lệ lớp [ĐO]

### 6.1. Theo file

| File | Hợp lệ | Normal (0) | Attack (1) | % attack | Normal : attack | CAN ID khác nhau |
|---|---:|---:|---:|---:|---:|---:|
| DoS | 3.665.771 | 3.078.250 | 587.521 | 16,03 | 5,24 : 1 | 27 |
| Fuzzy | 3.838.860 | 3.347.013 | 491.847 | 12,81 | 6,80 : 1 | 2.048 |
| gear | 4.443.142 | 3.845.890 | 597.252 | 13,44 | 6,44 : 1 | 26 |
| RPM | 4.621.702 | 3.966.805 | 654.897 | 14,17 | 6,06 : 1 | 26 |
| normal TXT | 988.871 | 988.871 | 0 | không áp dụng | không áp dụng | 27 |
| **Tổng** | **17.558.346** | **15.226.829** | **2.331.517** | **13,28** | | |

Số khớp tuyệt đối với W02-B1, B3 EDA v1 và C3 (bốn cách cài đặt độc lập, cùng kết quả).

### 6.2. Ba cách đếm tổng, vì đoạn đuôi 891.068 dòng bị lặp ở 4 CSV

| Cách đếm | Số dòng | Attack | % attack |
|---|---:|---:|---:|
| 4 CSV, giữ nguyên | 16.569.475 | 2.331.517 | 14,07 |
| 4 CSV, đoạn đuôi tính một lần [SUY RA] | 13.896.271 | 2.331.517 | 16,78 |
| 4 CSV + normal TXT, đoạn đuôi một lần [SUY RA] | 14.885.142 | 2.331.517 | 15,66 |

Đa lớp (4 CSV, đoạn đuôi một lần) [SUY RA]: normal 11.564.754 (83,22%), dos 587.521 (4,23%), fuzzy 491.847 (3,54%), gear 597.252 (4,30%), rpm 654.897 (4,71%).

### 6.3. Theo split thời gian (mô phỏng A2: purged temporal 70/15/15, purge 1%)

[ĐO] mô phỏng lại **công thức** của `purged_temporal_split` trên timestamp thật (không chạy code A2). Cột "% attack".

| File | Chính sách đoạn đuôi | Train | Val | Test |
|---|---|---:|---:|---:|
| DoS | loại đoạn đuôi (mặc định A2) | 21,81 | 21,64 | 18,18 |
| Fuzzy | loại đoạn đuôi | 17,57 | 13,22 | 15,29 |
| gear | loại đoạn đuôi | 16,98 | 16,64 | 15,85 |
| RPM | loại đoạn đuôi | 17,46 | 18,47 | 16,88 |
| DoS | **giữ** đoạn đuôi | 21,81 | 15,40 | **0,00** |
| Fuzzy, gear, RPM | **giữ** đoạn đuôi | 16,7 đến 17,6 | **rỗng** | **0,00** (chỉ có đoạn đuôi) |

Bảng đầy đủ (số dòng từng split): `results/class_ratio_by_split.csv`.

---

## 7. Giới hạn đã biết (known issues)

| # | Vấn đề | Mức | Bằng chứng | Hướng xử lý (chưa chốt) |
|---|---|---|---|---|
| K1 | **Đoạn đuôi dùng chung**: 891.068 dòng giống hệt (hash byte-level trùng) ở cả 4 CSV, toàn nhãn R | Cao | `results/shared_tail_check.json` | D3 (mentor): giữ 1 bản hoặc loại. Không để nằm ở cả train và test |
| K2 | **Giữ đoạn đuôi + split theo thời gian làm hỏng đánh giá**: test không có attack nào ở cả 4 file; val rỗng ở Fuzzy, gear, RPM | Cao | mục 6.3 | Dùng "loại" hoặc "cô lập" đoạn đuôi (A2 mặc định đã là `exclude`) |
| K3 | **Một CAN ID gần như là nhãn**: DoS `0000` = 100% attack. Fuzzy: 2.010/2.048 ID chỉ xuất hiện ở attack, phủ 98,1% frame attack. gear `043f` và RPM `0316` lẫn cả normal (207.289 và 216.334 dòng) | Cao | `results/can_id_shortcut_risk.csv` | Báo cáo kèm ablation bỏ `can_id` (A2 đã có Baseline-B) |
| K4 | **Nhãn normal TXT là suy ra** từ tên file | Trung bình | mục 4 | Báo cáo tách riêng; chờ D4 |
| K5 | **Mỗi CSV chỉ có một loại tấn công**; mỗi file chỉ một xe, một phiên | Trung bình | schema | Ghi rõ giả định Non-IID khi chia client (D5) |
| K6 | **Mất cân bằng** 5,2 đến 6,8 : 1 | Trung bình | mục 6.1 | Dùng Precision/Recall/F1, confusion matrix; xử lý (class weight, v.v.) chờ mentor. A3 đang đề xuất `weighted_loss_preserve_raw_nk` |
| K7 | 1 dòng malformed: `normal_run_data.txt` dòng 988872, bị cụt | Thấp | `results/errors_sample.csv` | Log và loại (D7), không sửa |
| K8 | Chưa biết quan hệ giữa phần trước gap của các CSV có trùng nhau không | Chưa rõ | W02 mục 7 | Chưa kiểm; giả định độc lập |
| K9 | Tài liệu ghi 17 cột, thực tế 18 | Thấp | mục 3 | Sửa tài liệu |

---

## 8. Điểm chờ và phụ thuộc

| Mã | Nội dung | Ai chốt | Tình trạng khi ký phiên bản này |
|---|---|---|---|
| D1 | License HCRL khi có công ty SGOD | Mentor, bằng văn bản | Chưa có |
| D3 | Xử lý 4 gap và đoạn đuôi | Mentor, nhóm B | Chưa chốt |
| D4 | Binary hay multiclass | Mentor, A | Chưa chốt |
| D5 | Chia client FL | Mentor, C | Chưa chốt |
| D6 | Thêm `label_provenance`, `segment_id` vào schema v2 | B2 | Chưa chốt |
| C1/C2 | Output pipeline thật; mục 5 và các số sau pipeline | Nhóm C | **Chưa có**; kiểm tra output sau pipeline chưa làm |
| B2-W03 | Leakage, version dataset, normalization | B2 | **Chưa có**; mục 5 ghi theo A2 |

Khi C khóa pipeline (04/12): chạy lại `validate_dataset.py` trỏ vào output của C, đối chiếu mục 3 và 5, cập nhật lên v1.0 chính thức.

---

## 9. Tái lập

```bash
python scripts/validate_dataset.py --data-dir <thư mục raw> --out-dir results   # vài phút (17,5 triệu dòng), 21 kiểm tra
python -m unittest discover -s tests -v                                        # 6 test biên
```

Tất định (không dùng random). Python 3.10+, pandas, numpy. Log chạy: `logs/validate_run_2026-11-27.log`.
