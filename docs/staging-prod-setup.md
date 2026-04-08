# Staging + Prod Setup

## Mục tiêu

- `test.plxeditor.com` chạy môi trường `staging`
- `plxeditor.com` chạy môi trường `prod`
- Server tự theo dõi nhánh `staging` và `prod`, khi có commit mới sẽ tự pull và `docker compose up -d --build`
- `-staging` và `-prod` chỉ là deploy worktree, không phải nơi chỉnh code

## Thư mục deploy trên VPS

### Backend

- `/home/vpsroot/projects/backend/video-processing-service`:
  working copy hiện tại để phát triển
- `/home/vpsroot/projects/backend/video-processing-service-staging`:
  worktree chạy staging
- `/home/vpsroot/projects/backend/video-processing-service-prod`:
  worktree chạy production

### Frontend

- `/home/vpsroot/projects/frontend/video-processing-service-fe`:
  working copy hiện tại để phát triển
- `/home/vpsroot/projects/frontend/video-processing-service-fe-staging`:
  worktree chạy staging
- `/home/vpsroot/projects/frontend/video-processing-service-fe-prod`:
  worktree chạy production

## Script chính

- `scripts/setup-deploy-worktrees.sh`
- `scripts/deploy-staging.sh`
- `scripts/deploy-prod.sh`
- `scripts/sync-source-to-staging.sh`
- `scripts/promote-staging-to-prod.sh`
- `scripts/install-test-subdomain-host-nginx.sh`
- `scripts/auto-deploy-branches.sh`
- `scripts/install-auto-deploy-cron.sh`

## Chạy lần đầu

```bash
cd /home/vpsroot/projects/backend/video-processing-service
chmod +x scripts/*.sh
./scripts/setup-deploy-worktrees.sh
./scripts/install-test-subdomain-host-nginx.sh
./scripts/install-auto-deploy-cron.sh
```

## Quy tắc vận hành

- Chỉ chỉnh code ở:
  - `/home/vpsroot/projects/backend/video-processing-service`
  - `/home/vpsroot/projects/frontend/video-processing-service-fe`
- Không chỉnh tay trong:
  - `/home/vpsroot/projects/backend/video-processing-service-staging`
  - `/home/vpsroot/projects/backend/video-processing-service-prod`
  - `/home/vpsroot/projects/frontend/video-processing-service-fe-staging`
  - `/home/vpsroot/projects/frontend/video-processing-service-fe-prod`
- Các thư mục `-staging` và `-prod` luôn được reset sạch về `origin/staging` hoặc `origin/prod` trước khi deploy
- Frontend staging và prod dùng cùng `Dockerfile`; khác biệt môi trường nằm ở branch và compose, không nằm ở file build riêng ngoài branch

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

## Auto deploy safety

- `staging` auto deploy được bật sau lần chạy `./scripts/deploy-staging.sh` đầu tiên
- `prod` chỉ auto deploy sau lần chạy `./scripts/deploy-prod.sh` đầu tiên
- Cơ chế này tránh việc prod trên VPS tự nhảy sang branch khác trước khi bạn xác nhận

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
- Sau đó tự build lại docker staging từ worktree sạch
- Staging có thể test qua `https://test.plxeditor.com`

### 2. Promote staging sang production

```bash
cd /home/vpsroot/projects/backend/video-processing-service
./scripts/promote-staging-to-prod.sh
```

- Script này promote bằng branch `staging -> prod` cho cả backend và frontend
- Chỉ cho phép `fast-forward`, nếu có xung đột hoặc lệch lịch sử thì phải xử lý merge trong git trước
- Sau đó tự build lại docker production từ worktree sạch
- Production cập nhật ở `https://plxeditor.com`

### 3. Auto deploy theo branch

- Cron đang chạy mỗi phút:
  - `staging` branch mới -> tự deploy staging
  - `prod` branch mới -> tự deploy prod
- Cơ chế này chỉ hoạt động đầy đủ khi remote có branch tương ứng

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
