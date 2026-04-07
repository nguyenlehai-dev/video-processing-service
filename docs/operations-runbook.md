# Operations Runbook

## Chuẩn bị production

1. Điền đầy đủ secret thật vào `.env`
2. Đặt `STORAGE_BACKEND=r2`
3. Đảm bảo user chạy deploy có quyền Docker
4. Kiểm tra Cloudflare Tunnel hostname đang trỏ về `http://api:8000`

## Các lệnh vận hành chính

### Preflight

```bash
./scripts/preflight.sh
```

Script này sẽ:

- kiểm tra `.env`
- kiểm tra biến R2 quan trọng
- kiểm tra `SECRET_KEY`
- validate `docker compose config`
- báo tình trạng quyền truy cập Docker daemon

### Deploy

```bash
./scripts/deploy.sh
```

Script này sẽ:

- chạy preflight
- `docker compose up -d --build`
- in trạng thái service
- poll `http://127.0.0.1:8000/health`

### Kiểm tra sức khỏe service

```bash
./scripts/check-health.sh
./scripts/check-health.sh https://api.xyz.com
```

## Khắc phục lỗi Docker permission

Nếu gặp lỗi kiểu:

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

thì chạy bằng tài khoản có quyền Docker hoặc thêm user vào group `docker`:

```bash
sudo usermod -aG docker vpsroot
newgrp docker
docker ps
```

Nếu không muốn đổi group, có thể chạy lệnh deploy với `sudo`.

## Kiểm tra sau deploy

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f cloudflared
curl http://127.0.0.1:8000/health
curl https://api.xyz.com/health
```

## Checklist production

- `STORAGE_BACKEND=r2`
- `R2_PUBLIC_URL` là URL public thật
- `CLOUDFLARE_TUNNEL_TOKEN` không còn placeholder
- `docker compose ps` cho thấy `api` và `cloudflared` đang chạy
- `/health` trả về `storage_backend: r2`
