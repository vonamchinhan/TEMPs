# Chat End-to-End Encryption Demo

Dự án minh họa cách xây dựng một ứng dụng chat dùng WebSocket với mã hóa đầu-cuối (E2EE). Server chỉ đóng vai trò chuyển tiếp gói tin, nội dung tin nhắn được mã hóa bằng khóa đối xứng được tạo ra từ trao đổi khóa X25519 giữa các client.

## Tính năng chính

- Server WebSocket thuần túy, không đọc được nội dung tin nhắn.
- Client dòng lệnh tạo cặp khóa X25519 và thiết lập khóa chung với từng người tham gia.
- Mỗi tin nhắn được mã hóa bằng AES-GCM, mỗi người nhận có nonce riêng.
- Hỗ trợ nhiều người tham gia (theo mô hình phát tán), mỗi client giải mã được phần tin của mình.

## Yêu cầu hệ thống

- Python 3.10 hoặc mới hơn.
- Pip để cài đặt thư viện phụ thuộc.

Cài đặt thư viện:

```bash
python -m venv .venv
source .venv/bin/activate  # Trên Windows dùng .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Chạy server

```bash
python src/server.py
```

Server mặc định lắng nghe tại `ws://127.0.0.1:8765`.

## Chạy client

Mở một terminal mới cho mỗi người dùng và chạy:

```bash
python src/client.py
```

Sau khi nhập tên hiển thị và URL server (có thể nhấn Enter để dùng mặc định), client sẽ:

1. Sinh cặp khóa X25519 và gửi public key cho mọi người trong phòng.
2. Tự động thiết lập khóa bí mật với từng người khác khi nhận được `handshake`.
3. Mã hóa tin nhắn gửi đi bằng AES-GCM với khóa tương ứng từng người nhận.

> ⚠️ Demo này phục vụ mục đích học tập. Để dùng trong môi trường thực tế cần bổ sung xác thực, quản lý danh tính, chống tấn công trung gian, quản lý khóa, lưu trữ tin, v.v.

## Cấu trúc thư mục

```
src/
├── client.py        # Client dòng lệnh
├── encryption.py    # Hàm hỗ trợ tạo khóa, mã hóa, giải mã
└── server.py        # Server WebSocket chuyển tiếp tin nhắn
```

## Kiểm thử nhanh

Bạn có thể chạy kiểm tra cú pháp bằng:

```bash
python -m compileall src
```

Lệnh này đảm bảo các file Python không bị lỗi cú pháp trước khi triển khai.
