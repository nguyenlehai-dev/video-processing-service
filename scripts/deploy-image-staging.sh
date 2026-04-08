#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/vpsroot/projects/backend/video-processing-service"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.image.staging.yml"
DEPLOY_DIR="${ROOT_DIR}/deploy/staging"
APP_ENV_FILE="${DEPLOY_DIR}/.env"
APP_DATA_DIR="${DEPLOY_DIR}/data"

mkdir -p "${APP_DATA_DIR}"

if [[ ! -f "${APP_ENV_FILE}" ]]; then
  echo "[staging-image] Missing env file: ${APP_ENV_FILE}" >&2
  exit 1
fi

echo "[staging-image] Pulling staging images"
APP_ENV_FILE="${APP_ENV_FILE}" APP_DATA_DIR="${APP_DATA_DIR}" \
  docker compose -f "${COMPOSE_FILE}" -p video-processing-staging pull

echo "[staging-image] Starting staging containers from images"
APP_ENV_FILE="${APP_ENV_FILE}" APP_DATA_DIR="${APP_DATA_DIR}" \
  docker compose -f "${COMPOSE_FILE}" -p video-processing-staging up -d

echo "[staging-image] Waiting for API health"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8010/health >/dev/null 2>&1; then
    echo "[staging-image] API is healthy"
    exit 0
  fi
  sleep 2
done

echo "[staging-image] API did not become healthy in time" >&2
APP_ENV_FILE="${APP_ENV_FILE}" APP_DATA_DIR="${APP_DATA_DIR}" \
  docker compose -f "${COMPOSE_FILE}" -p video-processing-staging logs --tail=100 api >&2
exit 1
