# Báo cáo Chuyên sâu về Data Leakage & Kiểm soát Ranh giới Dữ liệu CAN Bus (SGOD-P1-W02-B2)

**Dự án:** SGOD — Xây dựng Hệ thống IDS bằng Học liên kết (FL) và Blockchain trên Mạng CAN Bus  
**Giai đoạn:** Phase 1 / Tuần 2 (W02) — Task B2  
**Tác giả:** Senior Data Engineer, ML Security Engineer & QA Lead  
**Ngày lập:** 23/11/2026  
**Trạng thái:** HOÀN THÀNH KIỂM CHỨNG KỸ THUẬT (Pending Reviewer Sign-off)

---

## 1. Tóm tắt Điều hành (Executive Summary)

Trong quá trình audit và kiểm thử pipeline tiền xử lý và chiến lược chia dữ liệu (Train/Val/Test split) cho bộ dữ liệu HCRL Car-Hacking Dataset, chúng tôi đã phát hiện và xử lý triệt để hai vấn đề cốt lõi liên quan đến **Data Leakage** và **Temporal Inversion**:

1. **Lỗi Đảo ngược Thời gian (Temporal Inversion):**
   - *Triệu chứng phát hiện:* `Train max timestamp > Test min timestamp: True`.
   - *Nguyên nhân gốc rễ (Root Cause):* Cả 4 file CSV (`DoS_dataset.csv`, `Fuzzy_dataset.csv`, `gear_dataset.csv`, `RPM_dataset.csv`) đều chứa một đoạn đuôi trùng lặp chính xác **891.068 dòng** ở cuối bản ghi (từ timestamp `1478200727.419470` đến `1478201209.058944`). Trước đây, theo đề xuất ban đầu (DEC-002), toàn bộ đoạn đuôi này bị gán cứng vào `train`. Khi chia dữ liệu trước đuôi thành train/val/test theo trình tự thời gian, tập `val` và `test` rơi vào mốc thời gian sớm hơn đoạn đuôi, dẫn đến việc tập `train` chứa dữ liệu tương lai muộn hơn `val` và `test`.
   - *Giải pháp đã triển khai:* Tách đoạn shared-tail khỏi phép đánh giá chính thông qua chính sách cấu hình `shared_tail_policy="exclude"` (hoặc `"isolate"`). Dữ liệu đánh giá chính được chia theo thứ tự thời gian nghiêm ngặt có purge gap, đảm bảo:
     $$\max(\text{Timestamp}_{\text{train}}) < \min(\text{Timestamp}_{\text{val}}) \le \max(\text{Timestamp}_{\text{val}}) < \min(\text{Timestamp}_{\text{test}})$$

2. **Phân định rõ CAN Periodic Content Hash Overlap vs. True Observation Identity Leakage:**
   - *Đặc thù mạng CAN ô tô:* Các ECU định kỳ phát quảng bá (periodic broadcast, 10–100Hz) các thông điệp trạng thái (ví dụ tốc độ, vòng tua, đèn báo). Khi trạng thái xe không đổi, nội dung payload (`can_id`, `dlc`, `data_0..7`) sẽ lặp lại hoàn toàn qua thời gian.
   - *Kết luận khoa học:* Việc trùng hash nội dung (`no_hash_overlap = False`) giữa các split là hiện tượng bình thường của mạng CAN, **không phải là data leakage**.
   - *Bản chất leakage thực sự:* Là sự trùng lặp thực thể quan sát `(source_file, source_line)` hoặc rò rỉ cửa sổ thời gian (window lookahead/crossing) hoặc rò rỉ nhãn (label leakage). Pipeline mới đã tách biệt hai khái niệm này, đạt **0 shared observation identities** giữa mọi cặp split.

---

## 2. Bằng chứng Thực nghiệm về Shared-Tail (891.068 Dòng Trùng lặp)

Kết quả xác minh toàn diện từ script `verify_shared_tail_full.py` trên toàn bộ 4 file CSV gốc:

| Tên File | Dòng Bắt đầu | Dòng Kết thúc | Tổng số dòng đuôi | Timestamp Bắt đầu | Timestamp Kết thúc | SHA-256 Chuẩn hóa |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `DoS_dataset.csv` | 2.774.703 | 3.665.770 | 891.068 | 1478200727.419470 | 1478201209.058944 | `224ee335210e7f733e06...` |
| `Fuzzy_dataset.csv` | 2.947.792 | 3.838.859 | 891.068 | 1478200727.419470 | 1478201209.058944 | `224ee335210e7f733e06...` |
| `gear_dataset.csv` | 3.552.074 | 4.443.141 | 891.068 | 1478200727.419470 | 1478201209.058944 | `224ee335210e7f733e06...` |
| `RPM_dataset.csv` | 3.730.634 | 4.621.701 | 891.068 | 1478200727.419470 | 1478201209.058944 | `224ee335210e7f733e06...` |

**Nhận xét:**
- Toàn bộ 891.068 dòng ở đuôi của cả 4 file có nhãn 100% là Normal (`R` / label 0).
- Chúng là cùng một lượt ghi (recording run) được nhà nghiên cứu HCRL nối vào đuôi của 4 kịch bản tấn công khác nhau.
- Nếu gộp 4 dataset lại để huấn luyện hoặc đánh giá theo kiểu truyền thống, hệ thống sẽ bị nhân bản **3.564.272 dòng** trùng lặp hoàn toàn, gây lệch trọng số nghiêm trọng trong Federated Learning.
- Nếu đưa một file vào train và file khác vào test mà không cô lập đoạn đuôi, 891.068 dòng này sẽ rò rỉ trực tiếp từ train sang test.

---

## 3. Chiến lược Xử lý Shared-Tail Đã Triển khai

Hàm `assign_split_groups` trong `scripts/w02_b2/split_strategy.py` hiện hỗ trợ tham số `shared_tail_policy`:

1. **`shared_tail_policy="exclude"` (Mặc định & Khuyến nghị):**
   - Toàn bộ các dòng thuộc khoảng timestamp shared-tail được gán nhãn `split = "excluded_shared_tail"`.
   - Các dòng này bị loại khỏi tập `train`, `val`, và `test`.
   - Phần dữ liệu chính (nơi diễn ra các đợt tấn công DoS, Fuzzy, Gear, RPM) được chia theo thứ tự thời gian với tỷ lệ 70% Train, 15% Val, 15% Test và có Purge Gap 1% ở ranh giới.
   - Đảm bảo tính toán vẹn thời gian: Train max timestamp luôn nhỏ hơn Test min timestamp.

2. **`shared_tail_policy="isolate"`:**
   - Gán `split = "shared_tail_eval"`.
   - Giữ lại 1 bản sao duy nhất làm tập kiểm thử tổng quát hóa (out-of-distribution / post-deployment test set) độc lập cho dữ liệu bình thường.

3. **`shared_tail_policy="train"` (Legacy DEC-002 mode):**
   - Gán vào `train` nhưng hệ thống cảnh báo nguy cơ đảo ngược thời gian nếu dữ liệu chứa các mốc sớm hơn.

4. **`shared_tail_policy="test"`:**
   - Gán vào `test` theo đúng thứ tự thời gian (vì xảy ra muộn nhất), nhưng lưu ý tập test sẽ bị pha loãng bởi 891k mẫu bình thường.

---

## 4. Bảng So sánh Chẩn đoán Trước và Sau khi Sửa Lỗi

Dưới đây là kết quả đo đạc thực tế từ công cụ chẩn đoán (`check_shared_tail_split.py` và `diagnose_split.py`):

| Tiêu chí | Trước khi sửa (Old Split) | Sau khi sửa (New Split - `exclude`) | Đánh giá |
| :--- | :--- | :--- | :--- |
| **Train Max Timestamp** | `1478200727.957717` (sau test!) | `1478198380.748942` | **Đã sửa triệt để** |
| **Val Min Timestamp** | `1478198380.816378` | `1478198380.816378` | Đồng nhất |
| **Val Max Timestamp** | `1478198381.688246` | `1478198381.688246` | Đồng nhất |
| **Test Min Timestamp** | `1478198381.761832` | `1478198381.761832` | Đồng nhất |
| **Test Max Timestamp** | `1478198382.666866` | `1478198382.666866` | Đồng nhất |
| **Train max > Test min** | **TRUE (Lỗi Temporal Leakage)** | **FALSE (Đạt chuẩn Chronological)** | **PASS** |
| **Shared Tail Rows in Train** | 1.000 dòng đuôi bị gán vào Train | 0 dòng (cô lập vào `excluded_shared_tail`) | **PASS** |
| **Purge Gap Train/Val** | 141 dòng (0.0674 giây) | 141 dòng (0.0674 giây) | **PASS** |
| **Purge Gap Val/Test** | 141 dòng (0.0736 giây) | 141 dòng (0.0736 giây) | **PASS** |
| **Observation Identity Overlap**| 0 dòng trùng | 0 dòng trùng | **PASS** |
| **CAN Content Hash Overlap** | 227 hash lặp (bình thường ở CAN) | 227 hash lặp (đã phân loại rõ là CAN periodic) | **INFO (Bình thường)** |

---

## 5. Kiểm soát Rò rỉ trong Trích xuất Đặc trưng (Feature Extraction)

Trong file `scripts/w02_b2/feature_extraction.py`:

1. **Reset Trạng thái Lịch sử tại Ranh giới Split:**
   - Để ngăn hiện tượng rò rỉ từ tương lai vào quá khứ qua các cửa sổ trượt (rolling window) như `rolling_mean_iat`, `rolling_std_iat`, và `can_id_freq_1s`:
   - Phím gom nhóm phân đoạn (`segment`) được định nghĩa kết hợp cả `source_file` và `split`:
     $$\text{Segment Key} = \text{source\_file} + \text{"\#\#"} + \text{split}$$
   - Khi chuyển từ dòng cuối của `train` sang dòng đầu của `val` hoặc `test`, toàn bộ biến động thời gian (`global_iat`, `inter_arrival_time`) được reset về `NaN`.
   - Các phép tính rolling hoàn toàn là nhân quả (causal / lookback-only), không sử dụng lookahead.

2. **Chống Rò rỉ Nhãn (Label Leakage Prevention):**
   - Bảng cấm `EXCLUDED_FIELDS` ngăn chặn tuyệt đối các cột:
     `{"flag_raw", "label", "attack_type", "source_file", "source_line", "label_provenance", "segment_id"}`.
   - Hàm `validate_no_label_leakage()` kiểm tra tự động trước khi xuất ma trận đặc trưng.

3. **Chống Rò rỉ Chuẩn hóa (Scaler Leakage Prevention):**
   - Module `PreprocessingPipeline` chỉ thực hiện `fit()` trên tập `train`.
   - Hàm `check_scaler_fitted_on_train_only()` kiểm chứng độ lệch thống kê của scaler so với train và val.

---

## 6. Kết luận & Khuyến nghị Bàn giao

1. **Khẳng định Kỹ thuật:**
   - Toàn bộ pipeline đã loại bỏ nguy cơ data leakage giữa Train, Val và Test.
   - Thứ tự thời gian được bảo toàn tuyệt đối cho bài toán phát hiện xâm nhập trong tương lai.
   - Shared-tail 891.068 dòng đã được cô lập an toàn, ngăn chặn việc nhân bản dữ liệu giả định trong huấn luyện phân tán.

2. **Các Quyết định Trình Mentor / Reviewer:**
   - **DEC-002:** Phê duyệt chính sách mặc định loại bỏ shared-tail (`shared_tail_policy="exclude"`) thay vì gán vào train như đề xuất ban đầu của B1, nhằm bảo vệ tính nguyên vẹn thời gian.
   - **DEC-005:** Phê duyệt bổ sung cột `label_provenance` ('observed' cho CSV, 'inferred' cho TXT) vào Schema v2.
   - **DEC-007:** Lựa chọn Baseline-A (18 đặc trưng khung + 5 đặc trưng thời gian, có CAN ID) làm cấu hình chuẩn, kèm Baseline-B (không có CAN ID) phục vụ ablation study.
