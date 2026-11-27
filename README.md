# SGOD - Group 6: Intrusion Detection System (IDS)

Dự án xây dựng Hệ thống Phát hiện Xâm nhập (IDS) trên mạng phân tán ứng dụng công nghệ **Federated Learning (Học liên kết)** và **Blockchain**.

---

## Cấu trúc thư mục dự án

```text
SGOD-Group6-IDS/
├── configs/            # Cấu hình thí nghiệm và pipeline
├── data/               # Dữ liệu thô, đã xử lý và chia theo client
│   ├── raw/
│   ├── processed/
│   └── clients/
├── src/                # Mã nguồn xử lý dữ liệu và tiện ích cốt lõi
├── models/             # Kiến trúc mô hình IDS
├── training/           # Huấn luyện và đánh giá mô hình
├── federated/          # Logic Federated Learning và tổng hợp
├── blockchain/         # Hợp đồng thông minh và xác thực sổ cái
│   └── contracts/
├── security/           # Tiện ích bảo mật và toàn vẹn dữ liệu
├── infrastructure/     # Dockerfile và cấu hình hạ tầng
├── tests/              # Kiểm thử đơn vị và smoke test
├── checkpoints/        # Trọng số mô hình đã lưu
├── results/            # Kết quả đánh giá và log
├── docs/               # Tài liệu kỹ thuật và bàn giao
├── reports/            # Báo cáo theo giai đoạn
├── compose.yaml        # Điều phối dịch vụ container
├── requirements.txt    # Danh sách thư viện Python
├── .gitignore          # Các file/thư mục bỏ qua khi đẩy Git
└── README.md           # Tài liệu hướng dẫn tổng quan dự án
