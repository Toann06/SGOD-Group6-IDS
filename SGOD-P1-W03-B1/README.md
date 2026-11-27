# SGOD-P1-W03-B1: kiểm tra dữ liệu sạch, nhãn, tỷ lệ lớp, data dictionary cuối

Trạng thái: v1.0-rc1, 27/11/2026, chờ B2 review. Điểm chờ: output pipeline C1/C2, kết quả B2-W03, quyết định D1/D3/D4/D5/D6 của mentor.

| Thư mục | Nội dung |
|---|---|
| `docs/data_dictionary_v1.md` | Từ điển dữ liệu (đầu ra chính) |
| `docs/B1_W03_data_quality_report.md` | Báo cáo kiểm tra chất lượng |
| `scripts/validate_dataset.py` | Script kiểm tra, chạy lại được |
| `tests/test_validate_dataset.py` | 6 test biên |
| `results/` | Bảng và JSON kết quả trên dữ liệu thật |
| `logs/` | Log chạy ngày 27/11/2026 |

Chạy lại (Python 3.10+, pandas, numpy; raw đặt ngoài repo):

    python scripts/validate_dataset.py --data-dir <thư mục raw> --out-dir results
    python -m unittest discover -s tests -v

Kết quả đã lưu: 21/21 kiểm tra PASS, 6/6 test PASS.
