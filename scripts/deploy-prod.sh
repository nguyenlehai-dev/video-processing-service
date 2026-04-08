#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/vpsroot/projects/backend/video-processing-service-prod"

"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/setup-deploy-worktrees.sh"

echo "[prod] Pulling backend prod"
git -C "${ROOT_DIR}" fetch origin prod
git -C "${ROOT_DIR}" reset --hard origin/prod
git -C "${ROOT_DIR}" clean -fdx -e .env -e .deploy-enabled -e data

echo "[prod] Pulling frontend prod"
git -C /home/vpsroot/projects/frontend/video-processing-service-fe-prod fetch origin prod
git -C /home/vpsroot/projects/frontend/video-processing-service-fe-prod reset --hard origin/prod
git -C /home/vpsroot/projects/frontend/video-processing-service-fe-prod clean -fdx

touch "${ROOT_DIR}/.deploy-enabled"

echo "[prod] Building and starting production containers"
docker compose -f "${ROOT_DIR}/docker-compose.prod.yml" -p video-processing-service up -d --build

echo "[prod] Waiting for API health"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "[prod] API is healthy"
    exit 0
  fi
  sleep 2
done

echo "[prod] API did not become healthy in time" >&2
docker compose -f "${ROOT_DIR}/docker-compose.prod.yml" -p video-processing-service logs --tail=100 api >&2
exit 1
