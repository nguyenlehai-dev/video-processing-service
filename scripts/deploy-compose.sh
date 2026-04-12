#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-video-processing-be}"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  # Export APP_PORT / APP_CONTAINER_NAME from .env for docker compose interpolation.
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

cd "${ROOT_DIR}"
docker compose -p "${PROJECT_NAME}" up -d --build
docker compose -p "${PROJECT_NAME}" ps
