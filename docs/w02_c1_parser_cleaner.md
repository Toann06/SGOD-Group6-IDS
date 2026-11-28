# Parser/Cleaner CAN · P1-W2-C1

C1 đọc lần lượt năm tệp HCRL và xuất một dòng CSV cho mỗi khung CAN hợp lệ. Chương trình dùng thư viện chuẩn của Python 3.10 trở lên, xử lý theo dòng để dung lượng RAM không tăng theo số bản ghi.

## Chạy từ thư mục gốc của repository

Đặt trực tiếp trong `data/raw/` năm tệp có tên `DoS_dataset.csv`, `Fuzzy_dataset.csv`, `gear_dataset.csv`, `RPM_dataset.csv` và `normal_run_data.txt`. Với dữ liệu thật đã kiểm tra, cần khoảng 2 GB dung lượng trống cho một lần xuất.

```powershell
python src/c1_cleaner.py
```

Nếu dùng Python ngoài PATH, thay `python` bằng đường dẫn đến trình thông dịch. Để chạy lại và giữ kết quả trước đó, chọn một thư mục đầu ra mới.

```powershell
python src/c1_cleaner.py --input-dir data/raw --output-dir data/processed/w02_c1_run2
```

Sau khi xử lý đủ năm tệp, chương trình công bố ba tệp cùng lúc trong `data/processed/w02_c1/` hoặc thư mục đã chọn.

| Tệp | Nội dung |
|---|---|
| `frames.csv` | CSV UTF-8 có tiêu đề, phân cách bằng dấu phẩy. Giữ thứ tự vật lý trong mỗi tệp. |
| `errors.csv` | Một dòng cho mỗi bản ghi bị loại, gồm `source_file`, `source_line`, `reason` và `raw_line`. Các byte sai UTF-8 được hiển thị dưới dạng `\xNN`. |
| `summary.json` | Tổng số dòng đầu vào, hợp lệ, bị loại và số lỗi theo nguyên nhân. Theo từng tệp còn có SHA-256 của dữ liệu gốc và số bản ghi theo `attack_type`. |

Dòng dữ liệu lỗi được ghi nhận rồi chương trình tiếp tục. Mã thoát 0 cho biết đã xử lý hết các tệp, kể cả khi có dòng bị loại. Thiếu tệp, lỗi đọc/ghi hoặc đích đã tồn tại sẽ cho mã thoát khác 0. Chương trình chỉ mở tệp nguồn để đọc. Các thư mục kết quả có tên bắt đầu bằng `w02_c1` dưới `data/processed/`, thư mục tạm của C1 tại đó và các tệp nguồn nêu trên đã có quy tắc trong `.gitignore`.

## Dữ liệu đầu vào và quy tắc làm sạch

| Nguồn | Cấu trúc một dòng | Nhãn |
|---|---|---|
| Bốn CSV | Không có tiêu đề. Ba trường đầu là timestamp, CAN ID và DLC, tiếp đến đúng DLC byte rồi đến cờ. DLC bằng 0 vẫn có cờ. | `R` → `0/normal`. `T` → `1` và loại tương ứng với tên tệp (`dos`, `fuzzy`, `gear`, `rpm`). |
| TXT | `Timestamp: <ts> ID: <id> <trường phụ> DLC: <n> <payload>`. Các trường phân cách bằng khoảng trắng. Dữ liệu quan sát được dùng `000` ở trường phụ. | `0/normal`, cờ để trống, nhãn suy ra từ nguồn. |

Timestamp phải là số thập phân không âm, hữu hạn, được giữ nguyên độ chính xác dạng chuỗi. CAN ID là chuỗi hex trong giới hạn 29 bit. DLC là số nguyên từ 0 đến 8. Mỗi byte hiện diện phải có hai ký tự hex. Cleaner chuẩn hóa chữ hex thành chữ thường, giữ các số 0 đầu và để trống các vị trí ngoài DLC. Nó giữ các khung trùng giữa các tệp, gồm cả phần đuôi chung, để bảo toàn bản ghi và vị trí nguồn.

Các cột bàn giao dùng đúng thứ tự sau.

```text
timestamp,can_id,dlc,data_0,data_1,data_2,data_3,data_4,data_5,data_6,data_7,flag_raw,label,attack_type,source_file,source_line,label_provenance
```

16 cột đầu theo schema B2 trong manifest B3. Cột tùy chọn `label_provenance` nhận `observed_flag` hoặc `inferred_from_source`. C1 chưa có quy tắc phân đoạn được phê duyệt nên bỏ cột tùy chọn `segment_id`. `source_line` đếm từ 1, kể cả khi giữa hai bản ghi hợp lệ có dòng lỗi. Khi đọc CSV đầu ra, nên đọc CAN ID, timestamp và payload dưới dạng chuỗi để bảo toàn `0130`, `00` và phân biệt ô rỗng.

| Mã lỗi | Nguyên nhân |
|---|---|
| `empty_line`, `invalid_encoding` | Dòng trống hoặc byte đầu vào sai UTF-8. |
| `invalid_csv`, `missing_fields`, `invalid_normal_format` | CSV sai cú pháp, CSV thiếu trường cơ bản hoặc TXT thiếu cấu trúc bắt buộc. |
| `invalid_timestamp`, `invalid_can_id`, `invalid_dlc` | Giá trị tương ứng sai định dạng hoặc ngoài miền cho phép. |
| `invalid_flag` | Cờ cuối dòng CSV thiếu hoặc khác R/T sau chuẩn hóa. |
| `payload_length_mismatch`, `invalid_payload_byte` | Số trường payload khác DLC hoặc một byte trống/sai mã hex. |

Mỗi dòng bị loại được đếm một lần, theo lỗi đầu tiên phát hiện. Có thể đối chiếu tổng theo công thức `input = valid + invalid`.

## Kiểm thử

```powershell
python -m unittest discover -s tests -p "test_c1_cleaner.py" -v
python tests/verify_c1_real.py
```

Lệnh đầu dùng năm tệp nhỏ trong `tests/fixtures/w02_c1/` và thư mục tạm. Lệnh thứ hai xác minh lần chạy thật ở vị trí mặc định, đọc lại toàn bộ CSV đã xuất, năm tệp gốc và các mốc tham chiếu Git có sẵn trong repository. Phép đối chiếu dùng manifest và 18 bản ghi bàn giao B3 tại `2672e3e`, cùng bảng thống kê và mẫu lỗi B1 tại `14a7023`. Chạy cleaner trước khi chạy phép đối chiếu dữ liệu thật.
