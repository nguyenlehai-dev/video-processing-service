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

## Trình tự chuyển đổi an toàn

1. Push code lên `staging`
2. Chờ GitHub Actions build và push image `staging`
3. Chạy thử:
   - `scripts/deploy-image-staging.sh`
4. QA trên `test.plxeditor.com`
5. Promote `staging -> prod`
6. Chờ image `prod` được build
7. Chạy:
   - `scripts/deploy-image-prod.sh`
8. Chỉ sau khi prod ổn định mới xóa worktree:
   - frontend: `-staging`, `-prod`
   - backend: `-staging`, `-prod`

## Lưu ý

- Hiện production và staging live vẫn đang dùng flow cũ dựa trên worktree.
- Bộ file image-based mới chỉ là đường migration song song, chưa thay thế live flow.
