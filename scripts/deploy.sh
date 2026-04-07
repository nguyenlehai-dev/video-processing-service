#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[deploy] Running preflight checks"
"${ROOT_DIR}/scripts/preflight.sh"

echo "[deploy] Building and starting containers"
cd "${ROOT_DIR}"
docker compose up -d --build

echo "[deploy] Current service status"
docker compose ps

echo "[deploy] Waiting for API health check"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "[deploy] API is healthy"
    exit 0
  fi
  sleep 2
done

echo "[deploy] API did not become healthy in time" >&2
docker compose logs --tail=100 api >&2
exit 1
