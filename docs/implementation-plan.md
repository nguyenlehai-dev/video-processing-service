# Video Processing Service - Phân tích & Kế hoạch triển khai

## Tổng quan yêu cầu

Xây dựng một **Python API Service** sử dụng **FFmpeg** để xử lý video, chạy trên **Docker**, triển khai trên **VPS** và public qua **Cloudflare Tunnel** (ví dụ: `api.xyz.com`). Output video sau xử lý được upload lên **Cloudflare R2** và trả về URL cho client.

---

## Phân tích yêu cầu từ khách hàng

### Chức năng xử lý video (FFmpeg)

| # | Chức năng | Mô tả | FFmpeg Command (tham khảo) |
|---|-----------|--------|---------------------------|
| 1 | **Cắt video** | Cắt đoạn video theo thời gian bắt đầu/kết thúc | `ffmpeg -i input -ss 00:00:10 -to 00:00:30 output` |
| 2 | **Ghép video** | Nối nhiều video lại thành 1 | `ffmpeg -f concat -i list.txt output` |
| 3 | **Ghép âm thanh vào video** | Thêm/thay thế audio track | `ffmpeg -i video -i audio -c:v copy output` |
| 4 | **Tách âm thanh** | Trích xuất audio từ video | `ffmpeg -i input -vn -acodec copy output.mp3` |
| 5 | **Tăng/giảm tốc độ** | Thay đổi playback speed | `ffmpeg -i input -filter:v "setpts=0.5*PTS" output` |
| 6 | **Crop video** | Cắt vùng hiển thị | `ffmpeg -i input -filter:v "crop=w:h:x:y" output` |
| 7 | **Resize video** | Thay đổi kích thước | `ffmpeg -i input -vf scale=1280:720 output` |

### Luồng xử lý chính

```
Client gửi request (video + params)
        │
        ▼
┌─────────────────────────┐
│  API nhận video          │
│  Lưu vào /tmp/input.*   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  FFmpeg xử lý video     │
│  Output: /tmp/output.*  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Upload output lên      │
│  Cloudflare R2           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Trả về Response:       │
│  - URL file trên R2     │
│  - Metadata (size, etc) │
└─────────────────────────┘
```

### Yêu cầu bổ sung

| Yêu cầu | Chi tiết |
|----------|----------|
| **Quản lý User** | CRUD user, authentication (login/register) |
| **Quản lý API Key** | Tạo, thu hồi, xoá API key cho từng user |
| **Docker** | Build và chạy được trên Docker |
| **Cloudflare Tunnel** | Public service qua domain (VD: `api.xyz.com`) |
| **Cloudflare R2** | Lưu trữ video output, trả public URL |

---

## Proposed Changes - Kiến trúc hệ thống

### Tech Stack đề xuất

| Layer | Technology | Lý do |
|-------|-----------|-------|
| **Framework** | FastAPI (Python) | Async, tự động gen docs (Swagger), hiệu năng cao |
| **FFmpeg** | `subprocess` gọi trực tiếp FFmpeg CLI | Ổn định nhất, hỗ trợ đầy đủ tính năng |
| **Database** | SQLite (ban đầu) → PostgreSQL (mở rộng) | Đơn giản, không cần setup riêng, dễ migrate |
| **ORM** | SQLAlchemy + Alembic | Quản lý DB schema, migration |
| **Auth** | JWT (JSON Web Token) | Stateless, phổ biến cho API |
| **Storage** | Cloudflare R2 via `boto3` (S3-compatible) | SDK chính thức, ổn định |
| **Container** | Docker + Docker Compose | Bao gồm cả `cloudflared` tunnel |
| **Task Queue** | Background Tasks (FastAPI built-in) | Đủ cho giai đoạn đầu. Nâng cấp Celery + Redis nếu cần |

---

### Cấu trúc thư mục dự án

```
video-processing-service/
├── docs/
│   └── git-workflow.md              # [EXISTING] Git workflow
│
├── app/
│   ├── __init__.py
│   ├── main.py                      # [NEW] FastAPI entry point
│   ├── config.py                    # [NEW] Settings & environment vars
│   │
│   ├── api/                         # [NEW] API routes
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # [NEW] Main router aggregator
│   │   │   ├── auth.py              # [NEW] Login, Register, Refresh token
│   │   │   ├── users.py             # [NEW] CRUD users
│   │   │   ├── api_keys.py          # [NEW] CRUD API keys
│   │   │   └── video.py             # [NEW] Video processing endpoints
│   │   └── deps.py                  # [NEW] Dependencies (auth, db session)
│   │
│   ├── core/                        # [NEW] Core business logic
│   │   ├── __init__.py
│   │   ├── security.py              # [NEW] JWT, password hashing, API key verify
│   │   └── permissions.py           # [NEW] Role-based access control
│   │
│   ├── models/                      # [NEW] SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── user.py                  # [NEW] User model
│   │   ├── api_key.py               # [NEW] API Key model
│   │   └── job.py                   # [NEW] Processing job model (tracking)
│   │
│   ├── schemas/                     # [NEW] Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── auth.py                  # [NEW] Auth DTOs
│   │   ├── user.py                  # [NEW] User DTOs
│   │   ├── api_key.py               # [NEW] API Key DTOs
│   │   ├── video.py                 # [NEW] Video processing DTOs
│   │   └── job.py                   # [NEW] Job status DTOs
│   │
│   ├── services/                    # [NEW] Business services
│   │   ├── __init__.py
│   │   ├── video_service.py         # [NEW] FFmpeg wrapper logic
│   │   ├── storage_service.py       # [NEW] Cloudflare R2 upload/download
│   │   ├── user_service.py          # [NEW] User CRUD logic
│   │   └── api_key_service.py       # [NEW] API Key management logic
│   │
│   └── db/                          # [NEW] Database setup
│       ├── __init__.py
│       ├── session.py               # [NEW] DB session factory
│       └── base.py                  # [NEW] Base model
│
├── alembic/                         # [NEW] Database migrations
│   ├── versions/
│   └── env.py
├── alembic.ini                      # [NEW] Alembic config
│
├── tests/                           # [NEW] Unit & integration tests
│   ├── __init__.py
│   ├── test_video.py
│   ├── test_auth.py
│   └── test_api_keys.py
│
├── docker/                          # [NEW] Docker configs
│   └── Dockerfile                   # [NEW] Python + FFmpeg image
│
├── .env.example                     # [NEW] Environment template
├── .gitignore                       # [NEW] Git ignore rules
├── docker-compose.yml               # [NEW] App + Cloudflared tunnel
├── requirements.txt                 # [NEW] Python dependencies
└── README.md                        # [MODIFY] Project documentation
```

---

### API Endpoints

#### Auth (`/api/v1/auth`)

| Method | Endpoint | Mô tả | Auth |
|--------|----------|--------|------|
| `POST` | `/register` | Đăng ký user mới | ❌ Public |
| `POST` | `/login` | Đăng nhập, trả JWT | ❌ Public |
| `POST` | `/refresh` | Refresh access token | 🔑 JWT |
| `GET` | `/me` | Thông tin user hiện tại | 🔑 JWT |

#### Users (`/api/v1/users`) — Admin only

| Method | Endpoint | Mô tả | Auth |
|--------|----------|--------|------|
| `GET` | `/` | Danh sách users | 🔑 Admin |
| `GET` | `/{id}` | Chi tiết user | 🔑 Admin |
| `PUT` | `/{id}` | Cập nhật user | 🔑 Admin |
| `DELETE` | `/{id}` | Xoá user | 🔑 Admin |

#### API Keys (`/api/v1/api-keys`)

| Method | Endpoint | Mô tả | Auth |
|--------|----------|--------|------|
| `POST` | `/` | Tạo API key mới | 🔑 JWT |
| `GET` | `/` | Danh sách API keys của user | 🔑 JWT |
| `DELETE` | `/{id}` | Thu hồi (revoke) API key | 🔑 JWT |

#### Video Processing (`/api/v1/video`)

| Method | Endpoint | Mô tả | Auth |
|--------|----------|--------|------|
| `POST` | `/cut` | Cắt video | 🔑 API Key |
| `POST` | `/merge` | Ghép/nối nhiều video | 🔑 API Key |
| `POST` | `/add-audio` | Ghép âm thanh vào video | 🔑 API Key |
| `POST` | `/extract-audio` | Tách âm thanh từ video | 🔑 API Key |
| `POST` | `/speed` | Tăng/giảm tốc độ video | 🔑 API Key |
| `POST` | `/crop` | Crop video | 🔑 API Key |
| `POST` | `/resize` | Resize video | 🔑 API Key |
| `GET` | `/jobs/{job_id}` | Kiểm tra trạng thái job | 🔑 API Key |

> [!NOTE]
> Các endpoint video sử dụng **API Key** để xác thực (header `X-API-Key`), phù hợp cho việc tích hợp với các ứng dụng bên ngoài. Các endpoint quản lý (user, api-keys) sử dụng **JWT Bearer token**.

---

### Docker & Deployment

#### Dockerfile

```dockerfile
FROM python:3.12-slim

# Cài FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose (App + Cloudflare Tunnel)

```yaml
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data        # SQLite DB
      - /tmp/video-proc:/tmp    # Temp video files
    restart: unless-stopped
    networks:
      - app-net

  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    restart: unless-stopped
    depends_on:
      - api
    networks:
      - app-net

networks:
  app-net:
```

> [!IMPORTANT]
> Trong Cloudflare Zero Trust Dashboard, cần cấu hình **Public Hostname** trỏ domain (VD: `api.xyz.com`) → `http://api:8000`

---

### Environment Variables

```env
# App
APP_NAME=Video Processing Service
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database
DATABASE_URL=sqlite:///./data/app.db

# Cloudflare R2
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=video-output
R2_PUBLIC_URL=https://pub-xxx.r2.dev

# Cloudflare Tunnel
CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token
```

---

## Kế hoạch triển khai theo phases

### Phase 1: Foundation (Ưu tiên cao nhất)
- Setup project structure, FastAPI boilerplate
- Database models + migrations (User, API Key, Job)
- Auth system (JWT login/register)
- API Key management (CRUD)

### Phase 2: Video Processing Core
- FFmpeg video service (7 chức năng)
- Cloudflare R2 storage service (upload/download)
- Video API endpoints với job tracking
- File upload handling + temp file cleanup

### Phase 3: Docker & Deployment
- Dockerfile (Python + FFmpeg)
- Docker Compose (App + Cloudflared Tunnel)
- `.env` configuration
- Health check endpoint

### Phase 4: Polish & Testing
- API documentation (Swagger tự động từ FastAPI)
- Unit + integration tests
- Error handling & validation
- Rate limiting (optional)
- README documentation

---

## User Review Required

> [!IMPORTANT]
> **Xác nhận Tech Stack**: Sử dụng **FastAPI** + **SQLite** + **subprocess FFmpeg**. Nếu khách muốn dùng framework khác (Flask, Django) hoặc DB khác (PostgreSQL, MySQL) thì cần điều chỉnh.

> [!WARNING]
> **Xử lý đồng bộ vs bất đồng bộ**: Hiện plan sử dụng **FastAPI Background Tasks** cho video processing. Nếu khối lượng lớn (nhiều request đồng thời), cần nâng cấp lên **Celery + Redis**. Cần xác nhận quy mô sử dụng dự kiến.

> [!IMPORTANT]
> **Cloudflare R2 Credentials**: Cần được cung cấp Account ID, Access Key, Secret Key, Bucket Name để tích hợp. Hoặc có thể setup mock storage trước để test.

## Open Questions

1. **Database**: Dùng **SQLite** (đơn giản, không cần setup) hay **PostgreSQL** (mạnh hơn, cần thêm container)?
2. **Giới hạn file upload**: Giới hạn kích thước video upload tối đa bao nhiêu? (VD: 500MB, 1GB, 2GB?)
3. **R2 Public Access**: Video output có cần public URL trực tiếp hay cần presigned URL (bảo mật hơn)?
4. **User Roles**: Có bao nhiêu role? Chỉ cần **Admin** + **User** hay cần thêm?
5. **Rate Limiting**: Có cần giới hạn số request/phút cho mỗi API key không?

---

## Verification Plan

### Automated Tests
```bash
# Run unit tests
pytest tests/ -v

# Test API endpoints
pytest tests/ -v -k "test_video"

# Docker build test
docker compose build
docker compose up -d
curl http://localhost:8000/docs    # Swagger UI
curl http://localhost:8000/health  # Health check
```

### Manual Verification
- Upload video qua Swagger UI → kiểm tra output trên R2
- Test từng chức năng FFmpeg (cut, merge, crop, resize, speed, audio)
- Verify Cloudflare Tunnel connectivity từ domain public
- Test auth flow: register → login → create API key → call video API
