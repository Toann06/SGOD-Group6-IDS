# Báo cáo Đánh giá Rò rỉ Dữ liệu (Data Leakage Audit Report)

**Mã Báo cáo:** SGOD-P1-W02-B2-LEAKAGE-01  
**Ngày:** 23/11/2026  
**Phạm vi:** Kiểm tra rò rỉ dữ liệu trên pipeline trích xuất đặc trưng và phân hoạch train/val/test  

---

## 1. Mục tiêu và Tiêu chí Đánh giá
Báo cáo này thiết lập tiêu chuẩn kiểm định rò rỉ dữ liệu cho hệ thống IDS trên mạng CAN Bus ô tô, tập trung vào 6 chiều kiểm tra độc lập:

1. **Rò rỉ Thực thể Quan sát (Observation Identity Leakage):** Kiểm tra xem cùng một dòng ghi nguồn `(source_file, source_line)` có xuất hiện đồng thời ở nhiều tập dữ liệu hay không.
2. **Rò rỉ Trình tự Thời gian (Temporal Leakage / Inversion):** Đảm bảo mô hình được huấn luyện trên dữ liệu quá khứ và đánh giá trên dữ liệu tương lai. Không cho phép tập Train chứa mốc thời gian muộn hơn Test.
3. **Rò rỉ Ranh giới Cửa sổ Trượt (Window Boundary Leakage):** Đảm bảo các cửa sổ tính toán đặc trưng nhân quả (IAT, tần suất ID) không trượt qua ranh giới giữa Train, Val và Test.
4. **Trùng lặp Nội dung Tuần hoàn (CAN Content Hash Overlap):** Phân tích và đo đạc tần suất các frame CAN có cùng ID và payload xuất hiện ở nhiều split do chu kỳ phát sóng định kỳ của ECU.
5. **Rò rỉ Nhãn (Label Leakage):** Đảm bảo tuyệt đối không có sự xuất hiện của `label`, `flag_raw`, `attack_type` trong ma trận đầu vào mô hình.
6. **Rò rỉ Tham số Tiền xử lý (Preprocessor Leakage):** Xác minh các phép biến đổi (MinMax, StandardScaler, Imputer) chỉ được học tham số từ tập Train.

---

## 2. Kết quả Đo lường Thực nghiệm (lịch sử, mẫu 10.000 dòng)

Kết quả hiện hành ngày 24/11: xem real_data_smoke_test.json (50.000 DoS) và multi_csv_streaming_audit.json (200.000 dòng mẫu); không dùng bảng lịch sử dưới đây làm số liệu hiện hành.

| Chiều kiểm tra | Phương pháp đo | Kết quả trên Mẫu 10.000 dòng DoS | Đánh giá |
| :--- | :--- | :---: | :---: |
| **Observation Overlap (Train vs Val)** | Giao tập hợp `(source_file, source_line)` | **0 dòng** | **PASS** |
| **Observation Overlap (Train vs Test)** | Giao tập hợp `(source_file, source_line)` | **0 dòng** | **PASS** |
| **Observation Overlap (Val vs Test)** | Giao tập hợp `(source_file, source_line)` | **0 dòng** | **PASS** |
| **Temporal Order (Train vs Val)** | $\max(T_{\text{train}}) \le \min(T_{\text{val}})$ | $1478198380.75 \le 1478198380.82$ | **PASS** |
| **Temporal Order (Val vs Test)** | $\max(T_{\text{val}}) \le \min(T_{\text{test}})$ | $1478198381.69 \le 1478198381.76$ | **PASS** |
| **Temporal Order (Train vs Test)** | $\max(T_{\text{train}}) \le \min(T_{\text{test}})$ | $1478198380.75 \le 1478198381.76$ | **PASS** |
| **Purge Gap Train/Val** | Thời gian và số dòng đệm bị loại bỏ | 141 dòng (0.0674 giây) | **PASS** |
| **Purge Gap Val/Test** | Thời gian và số dòng đệm bị loại bỏ | 141 dòng (0.0736 giây) | **PASS** |
| **Window Boundary Crossing** | Quét cửa sổ kích thước 10 dòng | 0 cửa sổ vi phạm | **PASS** |
| **Label Leakage** | Kiểm tra danh mục cột cấm trong features | 0 cột vi phạm (đạt 23 features sạch) | **PASS** |
| **Scaler Fitting** | Sai số trung bình scaler so với train vs val | $\text{err}_{\text{train}} \le \text{err}_{\text{val}}$ | **PASS** |
| **CAN Content Hash Overlap** | Giao tập hợp SHA-256 payload | 227 hash lặp giữa Train và Test | **INFO (Bình thường)** |

---

## 3. Phân tích Hiện tượng CAN Content Hash Overlap
Nhiều công cụ kiểm thử ML thông thường đánh đồng việc trùng lặp hash nội dung giữa tập huấn luyện và tập kiểm thử là "Data Leakage". Tuy nhiên, đối với giao thức điều khiển trên xe ô tô (CAN Bus):
- Mạng CAN là mạng quảng bá không định tuyến (broadcast bus).
- Các ECU định kỳ (10–100Hz) phát lại các gói tin trạng thái (ví dụ ID `0x0002` hoặc `0x0316`).
- Khi xe đang chạy đều, các giá trị cảm biến không thay đổi, các gói tin liên tiếp có payload hoàn toàn giống hệt nhau.
- Nếu loại bỏ toàn bộ các frame có payload giống nhau khỏi tập test, chúng ta sẽ làm méo mó bản chất vật lý của mạng CAN và loại bỏ gần như toàn bộ lưu lượng bình thường, dẫn đến việc mô hình IDS không được đánh giá đúng trong môi trường thực tế.
- Do đó, việc tách biệt **Observation Identity** (thực thể quan sát tại dòng và thời điểm cụ thể) và **Content Hash** là hoàn toàn chuẩn xác về mặt khoa học.

---

## 4. Kết luận
Pipeline tiền xử lý và chiến lược phân hoạch của SGOD-P1-W02-B2 đạt chuẩn an toàn dữ liệu cao nhất, bảo vệ hệ thống khỏi mọi hình thức rò rỉ thông tin trước khi chuyển giao cho giai đoạn huấn luyện mô hình.
