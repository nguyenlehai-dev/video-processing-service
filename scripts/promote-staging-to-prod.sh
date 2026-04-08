#!/usr/bin/env bash
set -euo pipefail

PROJECTS_ROOT="/home/vpsroot/projects"

BACKEND_SOURCE="${PROJECTS_ROOT}/backend/video-processing-service"
FRONTEND_SOURCE="${PROJECTS_ROOT}/frontend/video-processing-service-fe"

promote_branch() {
  local source_repo="$1"
  local source_branch="$3"
  local target_branch="$4"
  local label="$5"

  git -C "${source_repo}" fetch origin "${source_branch}" "${target_branch}"
  git -C "${source_repo}" push origin "refs/remotes/origin/${source_branch}:refs/heads/${target_branch}"
  echo "[promote-prod] ${label}: ${source_branch} -> ${target_branch} pushed"
}

echo "[promote-prod] Promoting backend staging -> prod"
promote_branch "${BACKEND_SOURCE}" "staging" "prod" "backend"

echo "[promote-prod] Promoting frontend staging -> prod"
promote_branch "${FRONTEND_SOURCE}" "staging" "prod" "frontend"

echo "[promote-prod] Triggering production image deploy from remote branches"
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-image-prod.sh"
