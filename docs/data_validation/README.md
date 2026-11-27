# SGOD-P1-W2-C3 — Kiểm tra và xác thực dữ liệu CAN Bus

## 1. Giới thiệu

Module C3 được xây dựng nhằm kiểm tra tính hợp lệ và tính nhất quán của dữ liệu CAN Bus trước khi đưa vào các bước tiền xử lý (Preprocessing) và huấn luyện mô hình học liên kết (Federated Learning) trong dự án SGOD-IDS.

Module tập trung phát hiện các bản ghi có dữ liệu thiếu, sai định dạng hoặc không đáp ứng các quy tắc kiểm tra dữ liệu đã định nghĩa.

Các chức năng chính:

- Kiểm tra các trường dữ liệu bắt buộc.
- Kiểm tra định dạng Timestamp.
- Kiểm tra định dạng CAN ID.
- Kiểm tra giá trị DLC.
- Kiểm tra định dạng và độ dài Payload.
- Kiểm tra nhãn dữ liệu.
- Ghi log các bản ghi không hợp lệ kèm lý do.
- Thống kê số lượng bản ghi hợp lệ và không hợp lệ.
- Xuất báo cáo kiểm tra dữ liệu.

## 2. Cấu trúc dự án

Module C3 được tích hợp vào cấu trúc tổng thể của dự án SGOD-IDS như sau:

```text
SGOD-IDS/
├── blockchain/
│   └── contracts/
├── checkpoints/
├── configs/
├── data/
│   ├── clients/
│   ├── processed/
│   └── raw/
│       └── HCRL/                       # Dataset tải riêng
├── docs/
│   └── data_validation/
│       ├── README.md
│       └── SGOD-P1-W2-C3-report.md
├── federated/
├── infrastructure/
│   └── Dockerfile
├── models/
├── reports/
├── results/
│   ├── logs/
│   │   └── validation_errors.jsonl
│   └── validation/
│       └── validation_report.csv
├── scripts/
│   └── data_validation/
│       ├── run_b2_validation.py
│       ├── run_dataset_validation.py
│       ├── run_tests.py
│       └── run_validation_demo.py
├── security/
├── src/
│   └── data_validation/
│       ├── __init__.py
│       ├── logger.py
│       └── validator.py
├── tests/
│   └── unit/
│       └── data_validation/
│           ├── __init__.py
│           └── test_validator.py
├── training/
├── .gitignore
├── compose.yaml
├── README.md
└── requirements.txt
```

Các thành phần chính của module C3:

| Thành phần | Chức năng |
|---|---|
| `validator.py` | Chứa các quy tắc kiểm tra và hàm validation |
| `logger.py` | Ghi nhận thông tin các bản ghi không hợp lệ |
| `test_validator.py` | Kiểm thử các trường hợp dữ liệu hợp lệ và không hợp lệ |
| `run_dataset_validation.py` | Kiểm tra toàn bộ dataset HCRL |
| `run_b2_validation.py` | Kiểm tra dữ liệu theo quy trình hỗ trợ nhóm B2 |
| `run_validation_demo.py` | Minh họa hoạt động của validator |
| `validation_report.csv` | Báo cáo thống kê kết quả validation |
| `validation_errors.jsonl` | Log chi tiết các bản ghi không hợp lệ |

## 3. Dataset sử dụng

Dataset được sử dụng trong quá trình kiểm thử là **HCRL Car-Hacking Dataset**.

Nguồn dữ liệu chính thức:

[HCRL Car-Hacking Dataset](https://sites.google.com/hksecurity.net/hcrl/Datasets/car-hacking-dataset)

Các file dữ liệu được lưu tại:

```text
data/raw/HCRL/
```

| Dataset | Mô tả |
|---|---|
| `DoS_dataset.csv` | Dữ liệu tấn công Denial-of-Service |
| `Fuzzy_dataset.csv` | Dữ liệu tấn công Fuzzy |
| `gear_dataset.csv` | Dữ liệu tấn công Gear Spoofing |
| `RPM_dataset.csv` | Dữ liệu tấn công RPM Spoofing |
| `normal_run_data.txt` | Dữ liệu CAN Bus trong quá trình vận hành bình thường |

**Lưu ý:** Dataset được tải riêng và không đặt trực tiếp trong source code. Không nên đưa các file dataset dung lượng lớn vào Git repository.

## 4. Quy tắc kiểm tra dữ liệu

### 4.1. Các trường dữ liệu bắt buộc

Mỗi bản ghi CAN Bus sau khi chuẩn hóa cần có các trường:

| Trường | Mô tả |
|---|---|
| `timestamp` | Thời gian ghi nhận bản tin |
| `can_id` | Định danh bản tin CAN |
| `dlc` | Độ dài dữ liệu CAN |
| `payload` | Nội dung dữ liệu của bản tin |
| `label` | Nhãn phân loại dữ liệu |

### 4.2. Các quy tắc validation

| Trường | Quy tắc |
|---|---|
| `timestamp` | Giá trị số hợp lệ và không âm |
| `can_id` | Định dạng hexadecimal hợp lệ |
| `dlc` | Giá trị nguyên từ 0 đến 8 |
| `payload` | Phải có định dạng danh sách |
| Payload length | Độ dài payload phải khớp với DLC |
| Payload byte | Mỗi byte phải có đúng 2 ký tự hexadecimal |
| `label` | Giá trị phải thuộc tập `{0, 1}` |

Các bản ghi không đáp ứng một hoặc nhiều quy tắc trên sẽ được đánh dấu không hợp lệ và ghi nhận nguyên nhân lỗi.

## 5. Cài đặt môi trường

### 5.1. Yêu cầu

- Python 3.10 trở lên.
- Dataset HCRL được đặt trong thư mục `data/raw/HCRL/`.
- Thực hiện các lệnh từ thư mục gốc `SGOD-IDS/`.

Kiểm tra phiên bản Python:

```bash
python --version
```

### 5.2. Cài đặt thư viện

Nếu dự án có các thư viện bên ngoài được khai báo trong `requirements.txt`, cài đặt bằng lệnh:

```bash
pip install -r requirements.txt
```

Module validation hiện sử dụng các thành phần Python chuẩn như `csv`, `json`, `logging`, `pathlib` và `unittest`. Chỉ cần cài thêm thư viện nếu các thành phần khác của dự án yêu cầu.

## 6. Chạy kiểm thử

Tất cả các lệnh dưới đây được thực hiện từ thư mục gốc `SGOD-IDS/`.

### 6.1. Chạy Unit Test

```bash
python scripts/data_validation/run_tests.py
```

Unit test kiểm tra các trường hợp:

- Bản ghi hợp lệ.
- Thiếu trường dữ liệu.
- Timestamp không hợp lệ.
- CAN ID không hợp lệ.
- DLC bằng 0.
- DLC bằng 8.
- DLC nhỏ hơn 0.
- DLC lớn hơn 8.
- DLC sai kiểu dữ liệu.
- Payload không khớp với DLC.
- Payload sai định dạng.
- Payload chứa byte không hợp lệ.
- Label không hợp lệ.

### 6.2. Chạy kiểm tra toàn bộ dataset

```bash
python scripts/data_validation/run_dataset_validation.py
```

Chương trình xử lý lần lượt các dataset HCRL trong thư mục:

```text
data/raw/HCRL/
```

Các dataset CSV được đọc theo từng bản ghi.

Dataset Normal (`normal_run_data.txt`) được xử lý bằng parser riêng để chuyển dữ liệu CAN Bus từ định dạng text sang cấu trúc record chuẩn hóa trước khi validation.

Quá trình xử lý được thực hiện theo từng bản ghi nhằm hạn chế sử dụng bộ nhớ khi làm việc với các dataset có kích thước lớn.

### 6.3. Chạy chương trình demo

```bash
python scripts/data_validation/run_validation_demo.py
```

Chương trình minh họa hoạt động của validator với các bản ghi mẫu hợp lệ và không hợp lệ.

Kết quả hiển thị bao gồm tổng số bản ghi, số bản ghi hợp lệ và số bản ghi không hợp lệ. Các bản ghi lỗi cũng được ghi nhận thông qua validation logger.

### 6.4. Chạy kiểm tra dữ liệu hỗ trợ nhóm B2

```bash
python scripts/data_validation/run_b2_validation.py
```

Script hỗ trợ kiểm tra dữ liệu theo định dạng đầu vào được sử dụng trong quy trình làm việc với nhóm B2.

## 7. Kết quả kiểm tra

Kết quả kiểm tra thực tế trên dataset HCRL:

| Dataset | Tổng | Hợp lệ | Không hợp lệ |
|---|---:|---:|---:|
| DoS | 3,665,771 | 3,665,771 | 0 |
| Fuzzy | 3,838,860 | 3,838,860 | 0 |
| Gear | 4,443,142 | 4,443,142 | 0 |
| RPM | 4,621,702 | 4,621,702 | 0 |
| Normal | 988,872 | 988,871 | 1 |
| **Tổng** | **17,558,347** | **17,558,346** | **1** |

Tổng cộng 17,558,347 bản ghi đã được kiểm tra trên cả năm dataset.

Bốn dataset DoS, Fuzzy, Gear và RPM đều được kiểm tra thành công với tỷ lệ hợp lệ 100%.

Dataset Normal có 988,871 bản ghi hợp lệ và 1 bản ghi không hợp lệ, đạt tỷ lệ hợp lệ gần 100%.

### 7.1. Phân tích bản ghi không hợp lệ

Một bản ghi không đầy đủ được phát hiện tại cuối file `normal_run_data.txt`.

Nội dung bản ghi:

```text
Timestamp: 1479121941.287013
```

Bản ghi chỉ chứa Timestamp và thiếu các trường CAN ID, DLC và Payload.

Validation system đã phát hiện bản ghi không đáp ứng định dạng CAN Bus đã định nghĩa, từ chối bản ghi và ghi lại nguyên nhân lỗi vào validation log.

Dataset gốc được giữ nguyên, không tự động bổ sung hoặc thay đổi dữ liệu bị thiếu.

### 7.2. Tổng kết validation

Kết quả validation cho thấy:

- Các dataset DoS, Fuzzy, Gear và RPM đáp ứng toàn bộ các quy tắc validation đã định nghĩa.
- Dataset Normal được xử lý bằng parser riêng cho định dạng text.
- Một bản ghi không đầy đủ được phát hiện và ghi log.
- Tổng tỷ lệ bản ghi hợp lệ đạt khoảng 99.999994%.

Các kết quả này cho thấy module validation đã thực hiện việc kiểm tra các quy tắc định dạng và phát hiện bản ghi không đầy đủ trước khi dữ liệu được sử dụng trong các bước preprocessing tiếp theo.

## 8. File kết quả

Chương trình tạo báo cáo và log lỗi tại:

```text
results/
├── logs/
│   └── validation_errors.jsonl
└── validation/
    └── validation_report.csv
```

### 8.1. validation_report.csv

Chứa thống kê kiểm tra dữ liệu theo từng dataset, bao gồm:

- Dataset name.
- Total records.
- Valid records.
- Invalid records.
- Error rate.

### 8.2. validation_errors.jsonl

Chứa thông tin chi tiết các bản ghi bị lỗi, bao gồm:

- Thời gian ghi log.
- Dataset.
- Số thứ tự bản ghi.
- Nội dung bản ghi.
- Danh sách nguyên nhân lỗi.

### 8.3. Kết quả Unit Test

Unit Test được thực hiện bằng lệnh:

```bash
python scripts/data_validation/run_tests.py
```

Kết quả thực tế:

| Chỉ số | Kết quả |
|---|---:|
| Tổng số test | 17 |
| Test thành công | 17 |
| Test thất bại | 0 |
| Thời gian thực thi | 0,004 giây |
| Trạng thái | PASS |

Tất cả 17 test case đều thực thi thành công trong lần kiểm thử được ghi nhận.

## 9. Mục tiêu của task

**SGOD-P1-W2-C3: Dataset Validation and Edge Case Testing**

Mục tiêu là xây dựng module kiểm tra tính hợp lệ của dữ liệu CAN Bus, đảm bảo dữ liệu đầu vào được kiểm tra trước khi sử dụng cho các bước preprocessing và Federated Learning.

Các kết quả của task được sử dụng để:

- Phát hiện dữ liệu lỗi.
- Đánh giá chất lượng dataset.
- Xác định các vấn đề liên quan đến định dạng dữ liệu.
- Hỗ trợ xây dựng pipeline tiền xử lý dữ liệu.
- Đảm bảo khả năng tái thực hiện quá trình validation.

---

**Phạm vi của module:** C3 thực hiện kiểm tra tính hợp lệ về cấu trúc, định dạng và các quy tắc dữ liệu đã định nghĩa. Kết quả validation không đồng nghĩa với việc xác nhận bản tin CAN Bus là bình thường, độc hại hoặc đã được phát hiện tấn công chính xác.