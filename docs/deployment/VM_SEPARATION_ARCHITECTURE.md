# VM Separation Architecture - Video Processing Service

## Mục tiêu

Tài liệu này mô tả mô hình tách môi trường giống gatewave/getwave:

- `VM1` chạy `staging`
- `VM2` chạy `prod`
- backend và frontend đều tách riêng theo môi trường
- source repo và runtime path không trộn lẫn nhau

## Sơ đồ tổng thể

```text
                    GitHub
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
   branch staging            branch prod
          │                       │
          ▼                       ▼
      VM1 / Staging            VM2 / Production
   test.plxeditor.com            plxeditor.com
```

## VM1 - Staging

### Vai trò

- Dùng để QA
- Demo nội bộ hoặc cho khách xem trước
- Kiểm tra release trước khi promote production

### Runtime path

- Backend: `/home/vpsroot/apps/video-processing-staging/be`
- Frontend: `/home/vpsroot/apps/video-processing-staging/fe`

### Runtime config

- Backend branch: `staging`
- Frontend branch: `staging`
- Backend port: `18082`
- Frontend port: `8081`
- Backend container: `video-api-staging`
- Frontend container: `video-frontend-staging`
- Public domain: `test.plxeditor.com`

## VM2 - Production

### Vai trò

- Môi trường chạy thật cho người dùng
- Chỉ nhận code đã qua staging

### Runtime path

- Backend: `/home/vpsroot/apps/video-processing-prod/be`
- Frontend: `/home/vpsroot/apps/video-processing-prod/fe`

### Runtime config

- Backend branch: `prod`
- Frontend branch: `prod`
- Backend port: `18081`
- Frontend port: `8082`
- Backend container: `video-api-prod`
- Frontend container: `video-frontend-prod`
- Public domain: `plxeditor.com`

## Source Repo Chung

### Backend source

- `/home/vpsroot/projects/backend/video-processing-service`

### Frontend source

- `/home/vpsroot/projects/frontend/video-processing-service-fe`

Source repo là nơi:

- viết code
- tạo feature branch
- tạo PR
- review
- merge `dev -> staging -> prod`

Runtime path trong `apps` là nơi:

- checkout branch deploy
- lưu `.env`
- chạy container
- rollback / restart

## Release Flow

### Lên Staging

1. Merge feature vào `dev`
2. Promote `dev -> staging`
3. Trên VM1:

```bash
cd /home/vpsroot/apps/video-processing-staging/be && git pull origin staging && ./scripts/deploy-compose.sh
cd /home/vpsroot/apps/video-processing-staging/fe && git pull origin staging && ./scripts/deploy-compose.sh
```

### Lên Production

1. Xác nhận staging ổn định
2. Promote `staging -> prod`
3. Trên VM2:

```bash
cd /home/vpsroot/apps/video-processing-prod/be && git pull origin prod && ./scripts/deploy-compose.sh
cd /home/vpsroot/apps/video-processing-prod/fe && git pull origin prod && ./scripts/deploy-compose.sh
```

## Reverse Proxy

### Staging

- `test.plxeditor.com` -> frontend staging
- `/api`, `/health`, `/docs`, `/redoc`, `/openapi.json` -> backend staging

### Production

- `plxeditor.com` -> frontend production
- `/api`, `/health`, `/docs`, `/redoc`, `/openapi.json` -> backend production

## Ghi chú triển khai

- Path chuẩn hiện tại là:
  - `/home/vpsroot/apps/video-processing-staging`
  - `/home/vpsroot/apps/video-processing-prod`
- Legacy path vẫn được giữ dưới dạng symlink tương thích:
  - `/home/vpsroot/apps/gateway-staging`
  - `/home/vpsroot/apps/gateway-prod`
- Dự án đang chạy bên trong các path này là `video-processing-service`
- Nếu sau này đổi path vật lý lần nữa, cần cập nhật đồng bộ:
  - nginx / NPM
  - scripts deploy
  - backup jobs
  - monitoring
