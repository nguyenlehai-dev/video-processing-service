# Video Processing Service

API Service xử lý video sử dụng FFmpeg, xây dựng bằng Python (FastAPI), triển khai qua Docker và Cloudflare Tunnel.

## Tính năng

| Chức năng | Endpoint | Mô tả |
|-----------|----------|-------|
| 🎬 Cắt video | `POST /api/v1/video/cut` | Cắt đoạn video theo thời gian |
| 🔗 Ghép video | `POST /api/v1/video/merge` | Nối nhiều video lại thành 1 |
| 🔊 Ghép âm thanh | `POST /api/v1/video/add-audio` | Thêm/thay thế audio track |
| 🎵 Tách âm thanh | `POST /api/v1/video/extract-audio` | Trích xuất audio từ video |
| ⚡ Tốc độ | `POST /api/v1/video/speed` | Tăng/giảm playback speed |
| ✂️ Crop | `POST /api/v1/video/crop` | Cắt vùng hiển thị |
| 📐 Resize | `POST /api/v1/video/resize` | Thay đổi kích thước |

## Tech Stack

- **Framework:** FastAPI (Python 3.12)
- **Video:** FFmpeg (subprocess)
- **Database:** SQLite (SQLAlchemy ORM)
- **Auth:** JWT + API Key
- **Storage:** Cloudflare R2 (primary) with local fallback for development
- **Deploy:** Docker + Cloudflare Tunnel

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/nguyenlehai-dev/video-processing-service.git
cd video-processing-service
cp .env.example .env
# Edit .env with your actual credentials
```

### 2. Chạy với Docker (Production)

```bash
docker compose up -d --build
```

API sẽ chạy tại: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

### 3. Chạy local (Development)

```bash
# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc: venv\Scripts\activate  # Windows

# Cài dependencies
pip install -r requirements.txt

# Chạy app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Sử dụng API

### Bước 1: Đăng ký & Đăng nhập

```bash
# Đăng ký (user đầu tiên sẽ là admin)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","username":"admin","password":"admin123"}'

# Đăng nhập
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}'
```

### Bước 2: Tạo API Key

```bash
curl -X POST http://localhost:8000/api/v1/api-keys/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My App Key"}'
```

### Bước 3: Xử lý video

```bash
# Cắt video
curl -X POST http://localhost:8000/api/v1/video/cut \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "start_time=00:00:10" \
  -F "end_time=00:00:30"

# Resize video
curl -X POST http://localhost:8000/api/v1/video/resize \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "video=@input.mp4" \
  -F "width=1280" \
  -F "height=720"
```

### Bước 4: Kiểm tra trạng thái job

```bash
curl http://localhost:8000/api/v1/video/jobs/JOB_ID \
  -H "X-API-Key: YOUR_API_KEY"
```

## Cấu trúc thư mục

```
├── app/
│   ├── api/v1/          # API routes (auth, users, api-keys, video)
│   ├── core/            # Security (JWT, password hashing)
│   ├── db/              # Database session & base model
│   ├── models/          # SQLAlchemy models (User, ApiKey, Job)
│   ├── schemas/         # Pydantic DTOs
│   ├── services/        # Business logic (video, storage, user, api-key)
│   ├── config.py        # App settings
│   └── main.py          # FastAPI entry point
├── docker/Dockerfile    # Python + FFmpeg Docker image
├── docker-compose.yml   # App + Cloudflare Tunnel
├── docs/                # Documentation
└── tests/               # Unit & integration tests
```

## Tài liệu (Docs)

### Hướng dẫn sử dụng
- [📖 Hướng dẫn sử dụng API](docs/api-usage-guide.md) — Chi tiết tất cả endpoints, ví dụ curl

### Cấu hình & Triển khai
- [🚀 Deployment Workflow](docs/deployment-workflow.md) — Luồng deploy lên VPS
- [🌐 Cấu hình Cloudflare Tunnel](docs/cloudflare-tunnel-setup.md) — Public API qua domain
- [💾 Cấu hình Storage (R2)](docs/storage-setup.md) — Lưu trữ video output trên Cloudflare R2
- [🛠️ Operations Runbook](docs/operations-runbook.md) — Preflight, deploy, health check

### Quy trình làm việc
- [🔀 Git Workflow](docs/git-workflow.md) — Gitflow branching (prod/staging/dev)
- [📋 Implementation Plan](docs/implementation-plan.md) — Kế hoạch triển khai chi tiết

## License

Private - Internal use only.
