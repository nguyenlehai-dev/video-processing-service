# Hướng dẫn cấu hình Storage (Local)

Video output được lưu trữ **trực tiếp trên VPS** thay vì dịch vụ cloud (R2/S3). Đơn giản, miễn phí, không cần tài khoản bên thứ 3.

---

## Cách hoạt động

```
Upload video → FFmpeg xử lý → Lưu vào data/output/ → Download qua API
```

### Luồng chi tiết

```
1. Client upload video lên API  → POST /api/v1/video/cut
2. FFmpeg xử lý video           → Lưu file tạm vào /tmp/video-processing/
3. Copy output vào data/output/  → Xoá file tạm
4. Trả về download URL           → /api/v1/video/download/<filename>
5. Client download kết quả       → GET /api/v1/video/download/<filename>
```

---

## Cấu trúc thư mục trên VPS

```
~/video-processing-service/
├── data/
│   ├── app.db                    ← SQLite database
│   └── output/                   ← ⭐ Video output files
│       ├── <job-id>.mp4
│       ├── <job-id>.mp3
│       └── ...
└── docker-compose.yml
```

> **Quan trọng:** Thư mục `data/` được mount vào Docker container qua volume, nên dữ liệu **tồn tại vĩnh viễn** kể cả khi restart/rebuild container.

---

## Download file output

Sau khi xử lý xong, job sẽ trả về `output_url`:

```json
{
  "id": "abc-123",
  "status": "completed",
  "output_url": "/api/v1/video/download/abc-123.mp4"
}
```

Download:

```bash
# Download bằng curl
curl -O https://api.xyz.com/api/v1/video/download/abc-123.mp4

# Hoặc mở trong trình duyệt:
# https://api.xyz.com/api/v1/video/download/abc-123.mp4
```

> Download endpoint **không cần API Key** — file được truy cập qua URL trực tiếp sau khi có link.

---

## Quản lý dung lượng

### Kiểm tra dung lượng

```bash
# Tổng dung lượng output
du -sh ~/video-processing-service/data/output/

# Chi tiết từng file
ls -lhS ~/video-processing-service/data/output/

# Dung lượng ổ đĩa VPS
df -h /
```

### Dọn dẹp file cũ

```bash
# Xoá file output cũ hơn 30 ngày
find ~/video-processing-service/data/output/ -type f -mtime +30 -delete

# Xoá file output cũ hơn 7 ngày
find ~/video-processing-service/data/output/ -type f -mtime +7 -delete
```

### Tự động dọn dẹp (Cron job)

```bash
# Mở crontab
crontab -e

# Thêm dòng: xoá file hơn 30 ngày, chạy mỗi ngày lúc 3h sáng
0 3 * * * find /root/video-processing-service/data/output/ -type f -mtime +30 -delete
```

---

## So sánh với Cloud Storage

| Tiêu chí | Local Storage (hiện tại) | Cloudflare R2 |
|----------|------------------------|---------------|
| **Chi phí** | Miễn phí | $0.015/GB/tháng |
| **Setup** | Không cần cấu hình | Cần API token, bucket |
| **Tốc độ download** | Phụ thuộc VPS bandwidth | CDN toàn cầu |
| **Dung lượng** | Phụ thuộc ổ VPS (828GB free) | Không giới hạn |
| **Backup** | Tự backup | Tự động replicate |
| **Phù hợp** | Dự án nhỏ-vừa | Dự án lớn, nhiều user |

> 💡 Với VPS có 828GB free, local storage hoàn toàn đủ cho dự án hiện tại.

---

## Nâng cấp lên Cloud Storage (tương lai)

Nếu sau này cần, chỉ cần:

1. Tạo file `storage_service.py` mới kết nối R2/S3
2. Cập nhật `.env` với credentials
3. Rebuild Docker container

Code đã được thiết kế để dễ dàng swap storage backend.
