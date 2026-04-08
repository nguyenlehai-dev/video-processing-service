#!/usr/bin/env bash
set -euo pipefail

PROJECTS_ROOT="/home/vpsroot/projects"

BACKEND_SOURCE="${PROJECTS_ROOT}/backend/video-processing-service"
FRONTEND_SOURCE="${PROJECTS_ROOT}/frontend/video-processing-service-fe"
BACKEND_SOURCE_BRANCH="${BACKEND_SOURCE_BRANCH:-dev}"
FRONTEND_SOURCE_BRANCH="${FRONTEND_SOURCE_BRANCH:-dev}"

promote_branch() {
  local source_repo="$1"
  local source_branch="$3"
  local target_branch="$4"
  local label="$5"

  git -C "${source_repo}" fetch origin "${source_branch}" "${target_branch}"
  git -C "${source_repo}" push origin "refs/remotes/origin/${source_branch}:refs/heads/${target_branch}"
  echo "[sync-staging] ${label}: ${source_branch} -> ${target_branch} pushed"
}

echo "[sync-staging] Promoting backend branch ${BACKEND_SOURCE_BRANCH} -> staging"
promote_branch "${BACKEND_SOURCE}" "${BACKEND_SOURCE_BRANCH}" "staging" "backend"

echo "[sync-staging] Promoting frontend branch ${FRONTEND_SOURCE_BRANCH} -> staging"
promote_branch "${FRONTEND_SOURCE}" "${FRONTEND_SOURCE_BRANCH}" "staging" "frontend"

echo "[sync-staging] Triggering staging image deploy from remote branches"
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-image-staging.sh"
