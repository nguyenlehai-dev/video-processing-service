#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/vpsroot/projects/backend/video-processing-service-staging"

"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/setup-deploy-worktrees.sh"

echo "[staging] Pulling backend staging"
git -C "${ROOT_DIR}" fetch origin staging
git -C "${ROOT_DIR}" reset --hard origin/staging
git -C "${ROOT_DIR}" clean -fdx -e .env -e .deploy-enabled -e data

echo "[staging] Pulling frontend staging"
git -C /home/vpsroot/projects/frontend/video-processing-service-fe-staging fetch origin staging
git -C /home/vpsroot/projects/frontend/video-processing-service-fe-staging reset --hard origin/staging
git -C /home/vpsroot/projects/frontend/video-processing-service-fe-staging clean -fdx

touch "${ROOT_DIR}/.deploy-enabled"

echo "[staging] Building and starting staging containers"
docker compose -f "${ROOT_DIR}/docker-compose.staging.yml" -p video-processing-staging up -d --build

echo "[staging] Waiting for API health"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8010/health >/dev/null 2>&1; then
    echo "[staging] API is healthy"
    exit 0
  fi
  sleep 2
done

echo "[staging] API did not become healthy in time" >&2
docker compose -f "${ROOT_DIR}/docker-compose.staging.yml" -p video-processing-staging logs --tail=100 api >&2
exit 1
