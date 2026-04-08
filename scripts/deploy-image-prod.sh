#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/vpsroot/projects/backend/video-processing-service"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.image.prod.yml"
DEPLOY_DIR="${ROOT_DIR}/deploy/prod"
APP_ENV_FILE="${DEPLOY_DIR}/.env"
APP_DATA_DIR="${DEPLOY_DIR}/data"
BACKEND_SHA_FILE="${DEPLOY_DIR}/backend.sha"
FRONTEND_SHA_FILE="${DEPLOY_DIR}/frontend.sha"

mkdir -p "${APP_DATA_DIR}"

if [[ ! -f "${APP_ENV_FILE}" ]]; then
  echo "[prod-image] Missing env file: ${APP_ENV_FILE}" >&2
  exit 1
fi

echo "[prod-image] Pulling production images"
APP_ENV_FILE="${APP_ENV_FILE}" APP_DATA_DIR="${APP_DATA_DIR}" \
  docker compose -f "${COMPOSE_FILE}" -p video-processing-service pull

echo "[prod-image] Starting production containers from images"
APP_ENV_FILE="${APP_ENV_FILE}" APP_DATA_DIR="${APP_DATA_DIR}" \
  docker compose -f "${COMPOSE_FILE}" -p video-processing-service up -d

git -C "${ROOT_DIR}" fetch origin prod >/dev/null 2>&1 || true
git -C /home/vpsroot/projects/frontend/video-processing-service-fe fetch origin prod >/dev/null 2>&1 || true
git -C "${ROOT_DIR}" rev-parse "origin/prod" > "${BACKEND_SHA_FILE}" 2>/dev/null || true
git -C /home/vpsroot/projects/frontend/video-processing-service-fe rev-parse "origin/prod" > "${FRONTEND_SHA_FILE}" 2>/dev/null || true

echo "[prod-image] Waiting for API health"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "[prod-image] API is healthy"
    exit 0
  fi
  sleep 2
done

echo "[prod-image] API did not become healthy in time" >&2
APP_ENV_FILE="${APP_ENV_FILE}" APP_DATA_DIR="${APP_DATA_DIR}" \
  docker compose -f "${COMPOSE_FILE}" -p video-processing-service logs --tail=100 api >&2
exit 1
