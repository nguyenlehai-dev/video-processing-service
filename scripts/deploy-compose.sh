#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-video-processing-be}"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  while IFS='=' read -r key value; do
    case "${key}" in
      APP_PORT|APP_CONTAINER_NAME|COMPOSE_PROJECT_NAME)
        export "${key}=${value}"
        ;;
    esac
  done < <(grep -E '^(APP_PORT|APP_CONTAINER_NAME|COMPOSE_PROJECT_NAME)=' "${ROOT_DIR}/.env" || true)
fi

cd "${ROOT_DIR}"
docker compose -p "${PROJECT_NAME}" up -d --build
docker compose -p "${PROJECT_NAME}" ps
