# Staging + Prod Setup

## Mục tiêu

- Chỉ có **1 source gốc** để phát triển backend/frontend
- `test.plxeditor.com` chạy môi trường `staging`
- `plxeditor.com` chạy môi trường `prod`
- Server deploy bằng Docker image build theo branch
- Không còn phụ thuộc worktree `-staging` và `-prod` để chạy runtime

## Thư mục chuẩn trên VPS

### Backend

- `/home/vpsroot/projects/backend/video-processing-service`:
  working copy hiện tại để phát triển

### Frontend

- `/home/vpsroot/projects/frontend/video-processing-service-fe`:
  working copy hiện tại để phát triển

## Script chính

- `scripts/deploy-image-staging.sh`
- `scripts/deploy-image-prod.sh`
- `scripts/sync-source-to-staging.sh`
- `scripts/promote-staging-to-prod.sh`
- `scripts/install-test-subdomain-host-nginx.sh`
- `scripts/auto-deploy-branches.sh`
- `scripts/install-auto-deploy-cron.sh`

## Chạy lần đầu

```bash
cd /home/vpsroot/projects/backend/video-processing-service
chmod +x scripts/*.sh
./scripts/install-test-subdomain-host-nginx.sh
./scripts/install-auto-deploy-cron.sh
```

## Quy tắc vận hành

- Chỉ chỉnh code ở:
  - `/home/vpsroot/projects/backend/video-processing-service`
  - `/home/vpsroot/projects/frontend/video-processing-service-fe`
- Hai thư mục trên là source of truth duy nhất
- Deploy chỉ pull image `staging` hoặc `prod` từ GHCR
- Frontend staging dùng `Dockerfile.staging` để proxy cố định sang `video-api-staging`
- Frontend prod dùng `Dockerfile` mặc định trong network riêng của production

## Mapping domain

### Production

- `plxeditor.com` -> service `http://localhost:80`

### Staging

- `test.plxeditor.com` -> service `http://localhost:80`
- nginx host trên VPS sẽ route `test.plxeditor.com` sang `127.0.0.1:3010`

Nếu đang dùng Cloudflare Tunnel, chỉ cần để `Published application route` của `test.plxeditor.com` trỏ vào `http://localhost:80`.

## Ports local trên VPS

- Prod frontend: `3000`
- Prod API: `8000`
- Staging frontend: `3010`
- Staging API: `8010`

## Flow vận hành thực tế

### 1. Đưa bản cần QA lên staging

```bash
cd /home/vpsroot/projects/backend/video-processing-service
./scripts/sync-source-to-staging.sh
```

- Script này promote bằng branch:
  - backend: `dev -> staging`
  - frontend: `dev -> staging` mặc định
- Có thể đổi branch nguồn tạm thời:

```bash
BACKEND_SOURCE_BRANCH=dev FRONTEND_SOURCE_BRANCH=dev ./scripts/sync-source-to-staging.sh
```

- Script sẽ push lên remote `staging`
- Sau đó pull image `staging` mới nhất và deploy lại staging
- Staging có thể test qua `https://test.plxeditor.com`

### 2. Promote staging sang production

```bash
cd /home/vpsroot/projects/backend/video-processing-service
./scripts/promote-staging-to-prod.sh
```

- Script này promote bằng branch `staging -> prod` cho cả backend và frontend
- Chỉ cho phép `fast-forward`, nếu có xung đột hoặc lệch lịch sử thì phải xử lý merge trong git trước
- Sau đó pull image `prod` mới nhất và deploy lại production
- Production cập nhật ở `https://plxeditor.com`

### 3. Auto deploy theo branch

- Cron đang chạy mỗi phút:
  - `staging` branch mới -> tự deploy staging
  - `prod` branch mới -> tự deploy prod
- Script auto deploy so remote SHA với SHA đã deploy trong:
  - `deploy/staging/backend.sha`
  - `deploy/staging/frontend.sha`
  - `deploy/prod/backend.sha`
  - `deploy/prod/frontend.sha`

## Branch flow

### Backend

- `dev` -> `staging` -> `prod`

### Frontend

- Chuẩn vận hành:
  - `dev` -> `staging` -> `prod`

Remote branch `staging` và `prod` là bắt buộc để auto deploy hoạt động đúng.

## Ghi chú quan trọng

- Không dùng `rsync` để copy code giữa các môi trường nữa
- Promote chỉ đi qua branch và git history
- Frontend cần có remote branch `dev` để flow này vận hành đồng nhất với backend
- Worktree `-staging/-prod` chỉ còn là legacy cleanup target, không còn nằm trên đường deploy runtime
