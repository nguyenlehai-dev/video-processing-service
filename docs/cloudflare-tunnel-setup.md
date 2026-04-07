# Hướng dẫn cấu hình Cloudflare Tunnel

Cloudflare Tunnel cho phép public API ra internet mà **không cần mở port** trên firewall, **không cần public IP**.

---

## Bước 1: Tạo Tunnel trên Cloudflare Dashboard

1. Đăng nhập vào [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)
2. Vào menu **Networks** → **Tunnels**
3. Click **Create a tunnel**
4. Chọn **Cloudflared** → Đặt tên tunnel (VD: `video-api-tunnel`)
5. Copy **Tunnel Token** (chuỗi dài bắt đầu bằng `eyJ...`)

> ⚠️ **Lưu token này cẩn thận!** Chỉ hiển thị 1 lần.

---

## Bước 2: Cấu hình Public Hostname

Sau khi tạo tunnel, ở tab **Public Hostname**:

| Field | Giá trị |
|-------|---------|
| **Subdomain** | `api` (hoặc tên tùy chọn) |
| **Domain** | Chọn domain của bạn (VD: `xyz.com`) |
| **Type** | `HTTP` |
| **URL** | `http://api:8000` |

> **Lưu ý:** URL nên dùng **tên service Docker Compose** (`api`) chứ không phải `localhost`, vì `cloudflared` chạy trong Docker network cùng với API container.

Kết quả: `https://api.xyz.com` → Cloudflare → tunnel → service `api:8000`

---

## Bước 3: Cập nhật .env trên VPS

```bash
# SSH vào VPS
ssh vpsroot@ssh.vpspanel.io.vn

# Sửa file .env
cd ~/video-processing-service
nano .env
```

Cập nhật dòng:

```env
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoixxxxxxxxx...your-actual-token-here
```

---

## Bước 4: Restart container

```bash
sudo docker compose restart cloudflared

# Kiểm tra logs
sudo docker compose logs -f cloudflared
```

Nếu thấy log:
```
INF Registered tunnel connection
INF Connection registered
```

→ **Tunnel đã kết nối thành công!**

---

## Bước 5: Kiểm tra

```bash
# Từ bất kỳ máy nào có internet
curl https://api.xyz.com/health

# Kết quả mong đợi:
# {"status":"healthy","service":"Video Processing Service","version":"1.0.0"}
```

---

## Xử lý lỗi thường gặp

### Tunnel bị restart liên tục

```bash
sudo docker compose logs cloudflared
```

| Lỗi | Nguyên nhân | Cách sửa |
|-----|------------|----------|
| `failed to connect` | Token sai hoặc expired | Kiểm tra lại token trong `.env` |
| `Tunnel credentials file not found` | Token bị thiếu | Đảm bảo `CLOUDFLARE_TUNNEL_TOKEN` có trong `.env` |
| `connection refused` | API container chưa healthy | Chờ API start xong hoặc `sudo docker compose restart` |

### Truy cập domain bị lỗi 502

1. Kiểm tra API container còn chạy không: `sudo docker compose ps`
2. Kiểm tra Public Hostname URL trên Cloudflare Dashboard phải là `http://api:8000` (không phải `localhost`)
3. Đảm bảo cả 2 container cùng network (`app-net`)

---

## Kiến trúc mạng

```
Internet (HTTPS)
    │
    ▼
┌─────────────────────┐
│  Cloudflare Edge    │  ← SSL termination tự động
│  api.xyz.com        │
└─────────┬───────────┘
          │ (Encrypted tunnel)
          ▼
┌─────────────────────────────────────┐
│  VPS Docker (app-net network)       │
│                                     │
│  ┌─────────────┐  ┌──────────────┐ │
│  │ cloudflared  │→│ api          │ │
│  │ (tunnel)     │  │ :8000        │ │
│  └─────────────┘  └──────────────┘ │
└─────────────────────────────────────┘
```
