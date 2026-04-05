# Deployment Workflow - Video Processing Service

## Tổng quan luồng làm việc

```
┌─────────────────┐     git push      ┌──────────────┐    SSH + Docker     ┌─────────────────┐
│  Local Machine  │ ──────────────►  │    GitHub     │ ──────────────────► │   VPS Server    │
│  (Windows)      │                   │  Repository   │                     │  (Docker)       │
│                 │                   │               │                     │                 │
│  • Viết code    │                   │  • prod       │                     │  • docker compose│
│  • Test local   │                   │  • staging    │                     │  • cloudflared  │
│  • Commit/Push  │                   │  • dev        │                     │  • api.xyz.com  │
└─────────────────┘                   └──────────────┘                     └─────────────────┘
```

---

## Thông tin VPS

> ⚠️ **CẢNH BÁO BẢO MẬT:** Không nên lưu mật khẩu trong file git. Hãy đổi sang SSH Key authentication và password mạnh hơn sau khi setup xong.

| Thông tin | Giá trị |
|-----------|---------|
| **Host** | `ssh.vpspanel.io.vn` |
| **User** | `vpsroot` |
| **Password** | `123456789` |
| **Proxy** | Cloudflare Access SSH (`cloudflared`) |
| **Lệnh SSH** | `ssh vpsroot@ssh.vpspanel.io.vn` |

### Cấu hình SSH trên Windows (`~/.ssh/config`)

```
Host ssh.vpspanel.io.vn
    HostName ssh.vpspanel.io.vn
    User vpsroot

Host ssh.vpspanel.io.vn
    ProxyCommand "C:\Program Files (x86)\cloudflared\cloudflared.exe" access ssh --hostname %h
```

---

## Bước 1: Phát triển trên máy local (Windows)

### 1.1. Clone repo & chuyển sang nhánh `dev`

```bash
git clone https://github.com/nguyenlehai-dev/video-processing-service.git
cd video-processing-service
git checkout dev
```

### 1.2. Tạo nhánh feature để code

```bash
git checkout -b feat/video-cut-api
```

### 1.3. Code xong → commit & push

```bash
git add .
git commit -m "feat: add video cut endpoint #1"
git push origin feat/video-cut-api
```

### 1.4. Tạo PR trên GitHub: `feat/video-cut-api` → `dev` → Merge

---

## Bước 2: Deploy lên VPS qua SSH

### 2.1. Cấu trúc trên VPS

```
/home/user/
└── video-processing-service/     ← git clone repo ở đây
    ├── docker-compose.yml
    ├── .env                      ← file secrets (KHÔNG commit lên git)
    ├── data/                     ← SQLite database (persistent)
    └── ...
```

### 2.2. Lần đầu setup trên VPS

```bash
# SSH vào VPS (qua Cloudflare Access)
ssh vpsroot@ssh.vpspanel.io.vn

# Clone repo
git clone https://github.com/nguyenlehai-dev/video-processing-service.git
cd video-processing-service

# Chuyển sang nhánh cần deploy (staging hoặc prod)
git checkout staging

# Tạo file .env (chỉ cần làm 1 lần)
cp .env.example .env
nano .env   # Điền credentials thật

# Build & chạy Docker
docker compose up -d --build

# Kiểm tra
docker compose ps
docker compose logs -f api
```

### 2.3. Các lần deploy sau (cập nhật code mới)

```bash
# SSH vào VPS (qua Cloudflare Access)
ssh vpsroot@ssh.vpspanel.io.vn
cd video-processing-service

# Pull code mới
git pull origin staging    # hoặc prod

# Rebuild & restart
docker compose up -d --build

# Kiểm tra logs
docker compose logs -f api
```

---

## Bước 3: Cloudflare Tunnel tự động chạy

Cloudflare Tunnel chạy như **1 container Docker** trong `docker-compose.yml`, nên khi `docker compose up` thì tunnel cũng tự chạy luôn.

```
Internet                    VPS Docker
   │                           │
   │    api.xyz.com            │
   │         │                 │
   ▼         ▼                 │
┌──────────────────┐    ┌──────┴──────────────────────────┐
│  Cloudflare Edge │    │  docker compose                  │
│  (DNS + SSL)     │    │                                  │
│                  │◄───┤  ┌────────────┐ ┌─────────────┐ │
│  api.xyz.com     │    │  │cloudflared │ │  api:8000    │ │
│                  │    │  │  (tunnel)  │→│  (FastAPI +  │ │
└──────────────────┘    │  │            │ │   FFmpeg)    │ │
                        │  └────────────┘ └─────────────┘ │
                        │                                  │
                        │  Volume: ./data → SQLite DB      │
                        └──────────────────────────────────┘
```

**Kết quả:** Ai truy cập `https://api.xyz.com` → Cloudflare → tunnel → container `api:8000`

---

## Mapping Git branches → Environments

| Git Branch | Môi trường | VPS | Domain (ví dụ) | Mục đích |
|------------|-----------|-----|-----------------|----------|
| `dev` | Development | Local machine | `localhost:8000` | Phát triển & test |
| `staging` | Staging | VPS (hoặc chung VPS) | `staging-api.xyz.com` | QA & Demo cho khách |
| `prod` | Production | VPS | `api.xyz.com` | Người dùng thật |

### Trường hợp chỉ có 1 VPS (đơn giản nhất)

Nếu chỉ có **1 VPS**, có thể deploy trực tiếp nhánh `staging` hoặc `prod`:

```
Local (dev) ──push──► GitHub ──SSH pull──► VPS: ssh.vpspanel.io.vn
                                              │
                                              └─► docker compose up -d --build
                                              └─► Cloudflare Tunnel → api.xyz.com
```

**Luồng thực tế:**
1. Code trên local, merge PR vào `dev`
2. Khi ổn định → merge `dev` → `staging`
3. SSH vào VPS → `git pull origin staging` → `docker compose up -d --build`
4. Test trên `api.xyz.com`
5. OK → merge `staging` → `prod` → pull & rebuild trên VPS

---

## Các lệnh thường dùng trên VPS

### Docker

```bash
# Khởi động tất cả services
docker compose up -d --build

# Xem logs realtime
docker compose logs -f api
docker compose logs -f cloudflared

# Restart service
docker compose restart api

# Dừng tất cả
docker compose down

# Xem trạng thái
docker compose ps

# Truy cập vào container (debug)
docker compose exec api bash

# Xoá cache & rebuild hoàn toàn
docker compose down
docker system prune -f
docker compose up -d --build
```

### Git trên VPS

```bash
# Pull code mới nhất
git pull origin staging

# Xem đang ở nhánh nào
git branch

# Chuyển nhánh
git checkout prod
git pull origin prod
```

---

## Checklist setup VPS lần đầu

- [ ] SSH vào VPS thành công
- [ ] Đã cài Docker + Docker Compose
- [ ] Clone repo từ GitHub
- [ ] Tạo file `.env` với credentials thật:
  - [ ] `SECRET_KEY` (random string)
  - [ ] `R2_ACCOUNT_ID`
  - [ ] `R2_ACCESS_KEY_ID`  
  - [ ] `R2_SECRET_ACCESS_KEY`
  - [ ] `R2_BUCKET_NAME`
  - [ ] `R2_PUBLIC_URL`
  - [ ] `CLOUDFLARE_TUNNEL_TOKEN`
- [ ] Tạo Cloudflare Tunnel trên Zero Trust Dashboard
- [ ] Cấu hình Public Hostname → `http://api:8000`
- [ ] `docker compose up -d --build`
- [ ] Truy cập `https://api.xyz.com/docs` thấy Swagger UI
- [ ] Test upload video → nhận được R2 URL

---

## Quy trình deploy nhanh (tóm tắt)

```bash
# Trên Local: merge xong code vào staging
# Trên VPS:
ssh vpsroot@ssh.vpspanel.io.vn
cd video-processing-service
git pull origin staging
docker compose up -d --build
docker compose logs -f api     # kiểm tra logs
# Done! ✅
```


