# Image-Based Deploy

## Mục tiêu

Chuyển từ deploy dựa trên local worktree sang deploy dựa trên Docker image build theo branch.

## Registry

- Backend image: `ghcr.io/nguyenlehai-dev/video-processing-service-api`
- Frontend image: `ghcr.io/nguyenlehai-dev/video-processing-service-fe`

## Branch -> Tag Mapping

- `staging` -> tag `staging`
- `prod` -> tag `prod`

Ngoài ra workflow cũng push thêm tag dạng `sha-<commit>`.

## File mới

- Compose image-based staging:
  - `/home/vpsroot/projects/backend/video-processing-service/docker-compose.image.staging.yml`
- Compose image-based prod:
  - `/home/vpsroot/projects/backend/video-processing-service/docker-compose.image.prod.yml`
- Script deploy image-based:
  - `/home/vpsroot/projects/backend/video-processing-service/scripts/deploy-image-staging.sh`
  - `/home/vpsroot/projects/backend/video-processing-service/scripts/deploy-image-prod.sh`

## Env Files

- Staging env:
  - `/home/vpsroot/projects/backend/video-processing-service/deploy/staging/.env`
- Prod env:
  - `/home/vpsroot/projects/backend/video-processing-service/deploy/prod/.env`

Hai file này đang được tạo theo cấu hình đang chạy hiện tại để phục vụ migration.

## Trạng thái hiện tại

- `test.plxeditor.com` đã chạy bằng:
  - `ghcr.io/nguyenlehai-dev/video-processing-service-api:staging`
  - `ghcr.io/nguyenlehai-dev/video-processing-service-fe:staging`
- `plxeditor.com` đã chạy bằng:
  - `ghcr.io/nguyenlehai-dev/video-processing-service-api:prod`
  - `ghcr.io/nguyenlehai-dev/video-processing-service-fe:prod`
- Dữ liệu SQLite của staging/prod đã được copy sang `deploy/<env>/data`
- Script image deploy hiện ghi lại SHA đã deploy vào `deploy/<env>/*.sha`

## Trình tự vận hành chuẩn

1. Push code lên `staging`
2. Chờ GitHub Actions build và push image `staging`
3. Chạy thử:
   - `scripts/deploy-image-staging.sh`
4. QA trên `test.plxeditor.com`
5. Promote `staging -> prod`
6. Chờ image `prod` được build
7. Chạy:
   - `scripts/deploy-image-prod.sh`
8. Xác nhận auto deploy hoặc xóa cleanup target cũ nếu không còn cần

## Lưu ý

- Worktree cũ không còn cần cho runtime.
- Nếu còn lưu để tham chiếu ngắn hạn, không được dùng chúng để sửa code hay deploy.
