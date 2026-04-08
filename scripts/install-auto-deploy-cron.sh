#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="/home/vpsroot/projects/backend/video-processing-service/scripts/auto-deploy-branches.sh"
LOG_PATH="/home/vpsroot/projects/backend/video-processing-service/data/auto-deploy.log"
CRON_LINE="* * * * * ${SCRIPT_PATH} >> ${LOG_PATH} 2>&1"

mkdir -p "$(dirname "${LOG_PATH}")"

CURRENT_CRONTAB="$(crontab -l 2>/dev/null || true)"
if printf '%s\n' "${CURRENT_CRONTAB}" | grep -Fq "${SCRIPT_PATH}"; then
  echo "[cron] Auto deploy already installed"
  exit 0
fi

{
  printf '%s\n' "${CURRENT_CRONTAB}"
  printf '%s\n' "${CRON_LINE}"
} | crontab -

echo "[cron] Installed auto deploy cron"
