# SGOD-P1-W2-C3 — Báo cáo kiểm tra và xác thực dữ liệu CAN Bus

## 1. Thông tin task

| Nội dung              | Chi tiết                                                                                           |
| --------------------- | -------------------------------------------------------------------------------------------------- |
| Dự án                 | SGOD                                                                                               |
| Giai đoạn             | P1                                                                                                 |
| Tuần                  | W2                                                                                                 |
| Task ID               | C3                                                                                                 |
| Tên task              | Dataset Validation and Edge Case Testing                                                           |
| Requirement liên quan | REQ-03                                                                                             |
| Dataset sử dụng       | HCRL Car-Hacking Dataset                                                                           |
| Trạng thái            | Đã triển khai validator, xử lý các định dạng dataset và hoàn thành validation trên toàn bộ dataset |

---

## 2. Mục tiêu

Task C3 tập trung xây dựng module kiểm tra tính hợp lệ của dữ liệu CAN Bus trước khi đưa vào quá trình tiền xử lý và huấn luyện mô hình học liên kết trong hệ thống SGOD.

Các mục tiêu cụ thể:

- Xác định các quy tắc kiểm tra dữ liệu đầu vào.
- Phát hiện các bản ghi thiếu trường dữ liệu hoặc sai định dạng.
- Kiểm tra tính nhất quán giữa DLC và Payload.
- Kiểm tra giá trị CAN ID, Timestamp và Label.
- Xây dựng cơ chế ghi log các bản ghi không hợp lệ kèm nguyên nhân.
- Kiểm thử validator với dữ liệu biên và dữ liệu thực tế.
- Thống kê số lượng bản ghi hợp lệ và không hợp lệ trên các dataset HCRL.

---

## 3. Dataset sử dụng

Dataset được sử dụng trong task C3 là HCRL Car-Hacking Dataset.

**Nguồn dữ liệu:**

[https://sites.google.com/hksecurity.net/hcrl/Datasets/car-hacking-dataset](https://sites.google.com/hksecurity.net/hcrl/Datasets/car-hacking-dataset)

Các file dataset được sử dụng:

| STT | Dataset             | Mô tả                              |
| --- | ------------------- | ---------------------------------- |
| 1   | DoS_dataset.csv     | Dữ liệu tấn công Denial-of-Service |
| 2   | Fuzzy_dataset.csv   | Dữ liệu tấn công Fuzzy             |
| 3   | gear_dataset.csv    | Dữ liệu tấn công Gear Spoofing     |
| 4   | RPM_dataset.csv     | Dữ liệu tấn công RPM Spoofing      |
| 5   | normal_run_data.txt | Dữ liệu CAN Bus bình thường        |

Đường dẫn dataset trong cấu trúc dự án SGOD-IDS:

```text
SGOD-IDS/
└── data/
    └── raw/
        └── HCRL/
            ├── DoS_dataset.csv
            ├── Fuzzy_dataset.csv
            ├── gear_dataset.csv
            ├── RPM_dataset.csv
            └── normal_run_data.txt
```

Dataset được tải riêng từ nguồn chính thức, không lưu trực tiếp trong source code.

---

## 4. Phân tích và thiết kế validation

### 4.1. Cấu trúc bản ghi đầu vào

Validator sử dụng cấu trúc bản ghi CAN Bus đã được chuẩn hóa gồm các trường:

| Trường      | Kiểu dữ liệu | Ý nghĩa                          |
| ----------- | ------------ | -------------------------------- |
| `timestamp` | Numeric      | Thời gian ghi nhận bản tin       |
| `can_id`    | String       | CAN Identifier                   |
| `dlc`       | Integer      | Data Length Code                 |
| `payload`   | List         | Dữ liệu truyền trong bản tin CAN |
| `label`     | Integer      | Nhãn phân loại                   |

### 4.2. Các quy tắc kiểm tra

| Mã    | Trường          | Quy tắc kiểm tra                          |
| ----- | --------------- | ----------------------------------------- |
| VR-01 | Required fields | Các trường bắt buộc phải tồn tại          |
| VR-02 | Timestamp       | Giá trị phải là số hợp lệ và không âm     |
| VR-03 | CAN ID          | Phải có định dạng hexadecimal hợp lệ      |
| VR-04 | DLC             | Phải là số nguyên trong khoảng 0–8        |
| VR-05 | Payload         | Phải có định dạng danh sách               |
| VR-06 | Payload length  | Độ dài Payload phải khớp với DLC          |
| VR-07 | Payload bytes   | Mỗi byte phải có đúng 2 ký tự hexadecimal |
| VR-08 | Label           | Nhãn phải thuộc tập giá trị 0 hoặc 1      |

### 4.3. Các trường hợp dữ liệu biên

Các trường hợp được thiết kế để kiểm tra validator:

- Bản ghi thiếu Timestamp.
- Bản ghi thiếu CAN ID.
- Bản ghi thiếu DLC.
- Bản ghi thiếu Payload.
- Bản ghi thiếu Label.
- Timestamp không hợp lệ.
- CAN ID không đúng định dạng hexadecimal.
- DLC bằng 0.
- DLC bằng 8.
- DLC nhỏ hơn 0.
- DLC lớn hơn 8.
- DLC sai kiểu dữ liệu.
- Payload không khớp với DLC.
- Payload không phải danh sách.
- Payload chứa byte không hợp lệ.
- Byte Payload không đủ 2 ký tự.
- Label không thuộc tập `{0, 1}`.

---

## 5. Thiết kế hệ thống

Module validation được tổ chức thành các thành phần chính:

### 5.1. Validator

File:

```text
src/data_validation/validator.py
```

Chức năng:

- Kiểm tra các trường bắt buộc.
- Kiểm tra Timestamp.
- Kiểm tra CAN ID.
- Kiểm tra DLC.
- Kiểm tra Payload.
- Kiểm tra Label.
- Trả về danh sách lỗi khi bản ghi không hợp lệ.

### 5.2. Logger

File:

```text
src/data_validation/logger.py
```

Chức năng:

- Ghi lại các bản ghi không hợp lệ.
- Lưu tên dataset.
- Lưu số thứ tự bản ghi.
- Lưu danh sách nguyên nhân lỗi.
- Lưu thông tin bản ghi bị lỗi.

Log được lưu theo định dạng JSON Lines.

### 5.3. Dataset Validation Script

File:

```text
scripts/data_validation/run_dataset_validation.py
```

Chức năng:

1. Đọc dataset.
2. Phân tích bản ghi.
3. Chuyển dữ liệu về cấu trúc chuẩn.
4. Thực hiện validation.
5. Thống kê số bản ghi hợp lệ.
6. Thống kê số bản ghi không hợp lệ.
7. Ghi log lỗi.
8. Xuất báo cáo CSV.

Script hỗ trợ xử lý các định dạng dữ liệu khác nhau trong HCRL Car-Hacking Dataset, bao gồm dữ liệu CSV và dữ liệu Normal được lưu dưới dạng văn bản.

---

## 6. Quy trình thực hiện

Quy trình validation được triển khai như sau:

```text
HCRL Dataset
     |
     v
Read Dataset
     |
     v
Parse CAN Bus Record
     |
     v
Normalize Record Structure
     |
     v
Validate Record
     |
     +---------------------+
     |                     |
     v                     v
Valid Record          Invalid Record
     |                     |
     v                     v
Count Valid            Record Error
                           |
                           v
                     Write Error Log
     |
     v
Generate Validation Report
```

Quá trình đọc dữ liệu được thực hiện tuần tự nhằm hạn chế sử dụng bộ nhớ đối với các dataset có kích thước lớn.

Đối với các dataset CSV, chương trình sử dụng parser tương ứng để đọc các trường dữ liệu và chuẩn hóa bản ghi.

Đối với dataset Normal (`normal_run_data.txt`), chương trình sử dụng parser riêng để phân tích cấu trúc bản tin văn bản, trích xuất Timestamp, CAN ID, DLC và Payload trước khi đưa vào validator.

---

## 7. Kết quả kiểm thử trên dataset thực tế

### 7.1. Tổng quan

Chương trình đã được chạy trên toàn bộ 5 dataset trong HCRL Car-Hacking Dataset.

Tổng số bản ghi được xử lý:

**17.558.347 bản ghi**

Kết quả thống kê:

| Dataset  | Tổng số bản ghi |         Hợp lệ | Không hợp lệ |   Tỷ lệ hợp lệ |
| -------- | --------------: | -------------: | -----------: | -------------: |
| DoS      |       3.665.771 |      3.665.771 |            0 |           100% |
| Fuzzy    |       3.838.860 |      3.838.860 |            0 |           100% |
| Gear     |       4.443.142 |      4.443.142 |            0 |           100% |
| RPM      |       4.621.702 |      4.621.702 |            0 |           100% |
| Normal   |         988.872 |        988.871 |            1 |     99,999899% |
| **Tổng** |  **17.558.347** | **17.558.346** |        **1** | **99,999994%** |

### 7.2. Kết quả dataset DoS

| Chỉ số               |   Giá trị |
| -------------------- | --------: |
| Tổng bản ghi         | 3.665.771 |
| Bản ghi hợp lệ       | 3.665.771 |
| Bản ghi không hợp lệ |         0 |
| Tỷ lệ hợp lệ         |      100% |

**Kết quả:**

Dataset DoS được xử lý thành công. Toàn bộ 3.665.771 bản ghi đều đáp ứng các quy tắc validation hiện tại.

### 7.3. Kết quả dataset Fuzzy

| Chỉ số               |   Giá trị |
| -------------------- | --------: |
| Tổng bản ghi         | 3.838.860 |
| Bản ghi hợp lệ       | 3.838.860 |
| Bản ghi không hợp lệ |         0 |
| Tỷ lệ hợp lệ         |      100% |

**Kết quả:**

Dataset Fuzzy được xử lý thành công. Không phát hiện bản ghi vi phạm các quy tắc validation hiện tại.

### 7.4. Kết quả dataset Gear

| Chỉ số               |   Giá trị |
| -------------------- | --------: |
| Tổng bản ghi         | 4.443.142 |
| Bản ghi hợp lệ       | 4.443.142 |
| Bản ghi không hợp lệ |         0 |
| Tỷ lệ hợp lệ         |      100% |

**Kết quả:**

Dataset Gear được xử lý thành công. Toàn bộ bản ghi đều được validator chấp nhận.

### 7.5. Kết quả dataset RPM

| Chỉ số               |   Giá trị |
| -------------------- | --------: |
| Tổng bản ghi         | 4.621.702 |
| Bản ghi hợp lệ       | 4.621.702 |
| Bản ghi không hợp lệ |         0 |
| Tỷ lệ hợp lệ         |      100% |

**Kết quả:**

Dataset RPM được xử lý thành công. Không ghi nhận bản ghi không hợp lệ trong quá trình validation.

### 7.6. Kết quả dataset Normal

| Chỉ số               |    Giá trị |
| -------------------- | ---------: |
| Tổng bản ghi         |    988.872 |
| Bản ghi hợp lệ       |    988.871 |
| Bản ghi không hợp lệ |          1 |
| Tỷ lệ hợp lệ         | 99,999899% |

**Kết quả:**

Dataset Normal đã được xử lý thành công sau khi xây dựng parser riêng cho định dạng dữ liệu văn bản của file `normal_run_data.txt`.

Phần lớn các bản ghi đều được parse và validation thành công. Chỉ phát hiện một bản ghi không hợp lệ tại cuối file dữ liệu.

Bản ghi lỗi có nội dung:

```text
Timestamp: 1479121941.287013
```

Bản ghi này chỉ chứa Timestamp và thiếu các thông tin cần thiết khác như CAN ID, DLC và Payload.

**Nguyên nhân:**

Bản ghi cuối cùng của file dữ liệu không đầy đủ, không đáp ứng cấu trúc bản tin CAN Bus được yêu cầu bởi parser và validator.

Bản ghi này được đánh dấu không hợp lệ và ghi vào error log với nguyên nhân:

```text
Invalid Normal dataset format
```

Dữ liệu gốc được giữ nguyên, không thực hiện chỉnh sửa hoặc loại bỏ trực tiếp trên file dataset.

---

## 8. Phân tích kết quả

### 8.1. Các dataset DoS, Fuzzy, Gear và RPM

Bốn dataset tấn công đã được xử lý thành công với tổng cộng:

**16.569.475 bản ghi hợp lệ.**

Tỷ lệ validation của cả bốn dataset đạt 100%.

Điều này cho thấy dữ liệu của bốn dataset phù hợp với cấu trúc đầu vào và các quy tắc validation được triển khai trong chương trình.

### 8.2. Dataset Normal

Dataset Normal có tổng cộng 988.872 bản ghi.

Sau khi xây dựng parser riêng để hỗ trợ định dạng văn bản của dataset Normal, chương trình đã xử lý thành công 988.871 bản ghi.

Chỉ có một bản ghi không hợp lệ do thiếu thông tin CAN ID, DLC và Payload.

Tỷ lệ validation của dataset Normal đạt khoảng 99,999899%.

Kết quả này cho thấy parser đã xử lý thành công định dạng dữ liệu Normal và vấn đề còn lại nằm ở một bản ghi không đầy đủ trong dataset gốc.

### 8.3. Tổng quan chất lượng dữ liệu

Tổng cộng 17.558.347 bản ghi đã được đưa vào quá trình kiểm tra.

Trong đó:

- 17.558.346 bản ghi được validator chấp nhận.
- 1 bản ghi bị đánh dấu không hợp lệ.
- Tỷ lệ hợp lệ tổng thể đạt khoảng 99,999994%.

Kết quả validation cho thấy các dataset HCRL được sử dụng trong task C3 nhìn chung đáp ứng các quy tắc kiểm tra cấu trúc dữ liệu đã xây dựng.

Bản ghi không hợp lệ đã được phát hiện và ghi log. Điều này giúp cung cấp thông tin về chất lượng dữ liệu đầu vào trước khi thực hiện các bước preprocessing tiếp theo.

---

## 9. Kết quả kiểm thử các trường hợp biên

Các trường hợp kiểm thử được thiết kế và triển khai trong file:

```text
tests/unit/data_validation/test_validator.py
```

| Test Case | Nội dung                                   | Kết quả mong đợi |
| --------- | ------------------------------------------ | ---------------- |
| TC-01     | Bản ghi hợp lệ                             | Pass             |
| TC-02     | Thiếu trường bắt buộc                      | Fail             |
| TC-03     | DLC bằng 0                                 | Pass             |
| TC-04     | DLC bằng 8                                 | Pass             |
| TC-05     | DLC nhỏ hơn 0                              | Fail             |
| TC-06     | DLC lớn hơn 8                              | Fail             |
| TC-07     | DLC sai kiểu                               | Fail             |
| TC-08     | Payload không khớp DLC                     | Fail             |
| TC-09     | Payload sai định dạng                      | Fail             |
| TC-10     | Payload chứa byte hexadecimal không hợp lệ | Fail             |
| TC-11     | Payload byte sai độ dài                    | Fail             |
| TC-12     | Label bằng 0                               | Pass             |
| TC-13     | Label bằng 1                               | Pass             |
| TC-14     | Label không hợp lệ                         | Fail             |

Để thực thi unit test, sử dụng lệnh từ thư mục gốc `SGOD-IDS/`:

```bash
python scripts/data_validation/run_tests.py
```

### 9.1. Kết quả thực thi Unit Test

Unit Test được thực hiện bằng lệnh trên. Kết quả thực tế ghi nhận:

| Chỉ số             |    Kết quả |
| ------------------ | ---------: |
| Tổng số test       |         17 |
| Test thành công    |         17 |
| Test thất bại      |          0 |
| Thời gian thực thi | 0,004 giây |
| Trạng thái         |       PASS |

**Kết quả:** Cả 17 test đều thực thi thành công. Không có test nào thất bại.

Các nhóm kiểm thử bao gồm:

- Kiểm tra trường dữ liệu bắt buộc (Missing fields).
- Kiểm tra DLC với các giá trị biên và kiểu dữ liệu không hợp lệ.
- Kiểm tra Payload về kiểu dữ liệu, định dạng hexadecimal và độ dài.
- Kiểm tra Label hợp lệ và không hợp lệ.
- Kiểm tra bản ghi CAN Bus hợp lệ.

Kết quả cho thấy validator đáp ứng các trường hợp kiểm thử đơn vị đã xây dựng trong phạm vi task C3. Kết quả này không đồng nghĩa với việc đã kiểm chứng toàn bộ các tình huống có thể xuất hiện trong dữ liệu CAN Bus thực tế.

**Ghi chú:** Bảng test case liệt kê 14 nhóm trường hợp, trong khi kết quả thực thi ghi nhận 17 test. Cần đối chiếu trực tiếp với `test_validator.py` để liệt kê chính xác từng test case.

---

## 10. Kết quả đầu ra

Sau khi chạy chương trình validation, các file kết quả được tạo tại:

```text
SGOD-IDS/
└── results/
    ├── logs/
    │   └── validation_errors.jsonl
    └── validation/
        └── validation_report.csv
```

### 10.1. Validation Report

File:

```text
results/validation/validation_report.csv
```

Chứa thống kê validation của từng dataset:

- Tên dataset.
- Tổng số bản ghi.
- Số bản ghi hợp lệ.
- Số bản ghi không hợp lệ.
- Tỷ lệ validation.

### 10.2. Error Log

File:

```text
results/logs/validation_errors.jsonl
```

Chứa thông tin các bản ghi bị lỗi, bao gồm:

- Timestamp ghi log.
- Tên dataset.
- Số thứ tự bản ghi.
- Nguyên nhân lỗi.
- Nội dung bản ghi.

Error log hiện ghi nhận một bản ghi không hợp lệ thuộc dataset Normal.

---

## 11. Hướng dẫn thực hiện lại

Tất cả lệnh được thực hiện từ thư mục gốc `SGOD-IDS/`.

### Bước 1: Chạy Unit Test

```bash
python scripts/data_validation/run_tests.py
```

### Bước 2: Chạy validation trên dataset

```bash
python scripts/data_validation/run_dataset_validation.py
```

### Bước 3: Kiểm tra report

```text
results/validation/validation_report.csv
```

### Bước 4: Kiểm tra log lỗi

```text
results/logs/validation_errors.jsonl
```

---

## 12. Hạn chế và vấn đề còn tồn tại

- Validation hiện tập trung vào tính hợp lệ của cấu trúc dữ liệu, chưa thực hiện phát hiện tấn công.
- Các quy tắc validation hiện tại chưa đánh giá tính hợp lý của dữ liệu ở mức ngữ nghĩa hoặc hành vi CAN Bus.
- Một bản ghi cuối cùng trong dataset Normal không đầy đủ và đã được ghi nhận trong error log.
- Kết quả unit test cần được đối chiếu với output thực tế trước khi xác nhận hoàn thành kiểm thử.
- Chưa thực hiện đánh giá hiệu năng của validator trong các điều kiện triển khai thực tế khác nhau.

---

## 13. Kết luận

Task C3 đã triển khai module validation cho dữ liệu CAN Bus và thực hiện kiểm tra trên toàn bộ các dataset thuộc HCRL Car-Hacking Dataset.

Kết quả kiểm tra thực tế cho thấy cả năm dataset DoS, Fuzzy, Gear, RPM và Normal đã được xử lý thành công với tổng cộng 17.558.347 bản ghi.

Trong đó, 17.558.346 bản ghi hợp lệ và chỉ có một bản ghi không hợp lệ, đạt tỷ lệ validation tổng thể khoảng 99,999994%.

Dataset Normal đã được hỗ trợ thông qua parser riêng cho định dạng văn bản. Bản ghi không đầy đủ tại cuối file đã được phát hiện và ghi log.

Module validation cung cấp cơ sở để kiểm tra dữ liệu đầu vào, ghi log lỗi và thống kê dữ liệu trước khi đưa vào pipeline preprocessing và Federated Learning.

---

## 14. Bàn giao

### Deliverables

- [x] Module validator.
- [x] Error logger.
- [x] Unit test cho các trường hợp biên.
- [x] Dataset validation script.
- [x] Parser cho các định dạng dataset CSV và Normal text.
- [x] Chạy kiểm tra trên toàn bộ dataset HCRL.
- [x] Validation report.
- [x] Error log.
- [x] Ghi nhận kết quả thực tế.
- [x] Xử lý parser cho dataset Normal.
- [x] Chạy lại validation dataset Normal.
- [x] Xác nhận kết quả unit test.
- [ ] Review và xác nhận bàn giao.

### Reviewer

- Reviewer đề xuất: A4.
- Trạng thái review: Chưa xác nhận.

### Ghi chú

Các kết quả validation được ghi nhận dựa trên dữ liệu thực tế của HCRL Car-Hacking Dataset. Bản ghi không đầy đủ được giữ nguyên trong dataset gốc và được ghi nhận thông qua error log nhằm đảm bảo tính toàn vẹn của dữ liệu nguồn.

---

## 15. Blocker, giả định và các vấn đề cần xác nhận

### 15.1. Blocker

| STT | Vấn đề                                                                                 | Ảnh hưởng                                       | Trạng thái                                                     |
| --- | -------------------------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------- |
| 1   | Một bản ghi cuối file `normal_run_data.txt` không đầy đủ, thiếu CAN ID, DLC và Payload | Bản ghi không thể đưa qua validation thành công | Đã phát hiện, ghi log và xử lý bằng cách đánh dấu không hợp lệ |
| 2   | Chưa có xác nhận cuối cùng từ reviewer A4                                              | Chưa thể hoàn tất bước nghiệm thu task C3       | Đang chờ review                                                |

Hiện tại chưa ghi nhận blocker kỹ thuật nào ngăn cản việc tiếp tục sử dụng các bản ghi hợp lệ trong pipeline validation.

### 15.2. Giả định

| STT | Giả định                                                            | Cơ sở sử dụng                                      | Ghi chú                                                    |
| --- | ------------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------- |
| 1   | Cấu trúc bản ghi chuẩn gồm Timestamp, CAN ID, DLC, Payload và Label | Schema đầu vào được sử dụng trong module validator | Cần đối chiếu với schema thống nhất của nhóm               |
| 2   | DLC hợp lệ nằm trong khoảng 0–8                                     | Quy tắc validation hiện tại                        | Áp dụng cho cấu trúc CAN frame đang sử dụng                |
| 3   | Label thuộc tập giá trị 0 và 1                                      | Quy tắc validation hiện tại                        | Cần thống nhất cách ánh xạ nhãn với nhóm phụ trách dữ liệu |
| 4   | Bản ghi thiếu trường bắt buộc được xem là không hợp lệ              | Yêu cầu kiểm tra dữ liệu đầu vào                   | Không tự động bổ sung dữ liệu bị thiếu                     |

### 15.3. Quyết định cần mentor/reviewer xác nhận

- Xác nhận schema dữ liệu CAN Bus chuẩn dùng chung giữa các nhóm.
- Xác nhận quy tắc ánh xạ Label giữa dữ liệu Normal và các nhóm dữ liệu tấn công.
- Xác nhận cách xử lý bản ghi không đầy đủ: tiếp tục giữ nguyên và loại khỏi tập dữ liệu sử dụng hay áp dụng quy tắc xử lý khác.
- Xác nhận kết quả kiểm thử và nghiệm thu task C3.

### 15.4. Ghi chú

Các giả định trên được sử dụng để triển khai và kiểm thử module validation trong phạm vi task C3. Những nội dung chưa được mentor hoặc nhóm phụ trách dữ liệu xác nhận cần được giữ ở trạng thái giả định, không xem là quy chuẩn cuối cùng của toàn hệ thống.

---

## 16. Hướng dẫn tải dữ liệu và chạy Demo

### 16.1. Lưu ý về dữ liệu

Do bộ dữ liệu HCRL có dung lượng lớn và vượt quá giới hạn tải file lên ClickUp (60 MB), nhóm không đính kèm toàn bộ dataset trong gói bàn giao.

Reviewer có thể tải dữ liệu trực tiếp từ nguồn cung cấp chính thức tại Mục 3 – Dataset sử dụng của báo cáo.

**Dataset:** HCRL Car-Hacking Dataset
**Nguồn:** Korea University – HCRL

Sau khi tải dữ liệu, đặt các file vào đúng cấu trúc thư mục:

```text
SGOD-IDS/
└── data/
    └── raw/
        └── HCRL/
            ├── DoS_dataset.csv
            ├── Fuzzy_dataset.csv
            ├── gear_dataset.csv
            ├── RPM_dataset.csv
            └── normal_run_data.txt
```

### 16.2. Chạy kiểm thử

Tại thư mục gốc `SGOD-IDS/`, thực hiện:

```bash
python scripts/data_validation/run_tests.py
```

### 16.3. Chạy kiểm tra toàn bộ dataset

```bash
python scripts/data_validation/run_dataset_validation.py
```

### 16.4. Chạy chương trình demo

```bash
python scripts/data_validation/run_validation_demo.py
```

**Lưu ý:** Các đường dẫn và tên file dữ liệu cần khớp với cấu trúc mà script đang sử dụng. Kết quả chạy có thể khác nếu phiên bản hoặc nội dung dataset thay đổi.
