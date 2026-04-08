#!/usr/bin/env bash
set -euo pipefail

PROJECTS_ROOT="/home/vpsroot/projects"

BACKEND_SOURCE="${PROJECTS_ROOT}/backend/video-processing-service"
BACKEND_STAGING="${PROJECTS_ROOT}/backend/video-processing-service-staging"
FRONTEND_SOURCE="${PROJECTS_ROOT}/frontend/video-processing-service-fe"
FRONTEND_STAGING="${PROJECTS_ROOT}/frontend/video-processing-service-fe-staging"
BACKEND_SOURCE_BRANCH="${BACKEND_SOURCE_BRANCH:-dev}"
FRONTEND_SOURCE_BRANCH="${FRONTEND_SOURCE_BRANCH:-dev}"

"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/setup-deploy-worktrees.sh"

promote_branch() {
  local source_repo="$1"
  local target_repo="$2"
  local source_branch="$3"
  local target_branch="$4"
  local label="$5"

  git -C "${source_repo}" fetch origin "${source_branch}" "${target_branch}"
  git -C "${target_repo}" reset --hard "origin/${target_branch}"
  git -C "${target_repo}" clean -fdx -e .env -e .deploy-enabled -e data
  git -C "${target_repo}" merge --ff-only "origin/${source_branch}"
  git -C "${target_repo}" push origin "${target_branch}"
  echo "[sync-staging] ${label}: ${source_branch} -> ${target_branch} pushed"
}

echo "[sync-staging] Promoting backend branch ${BACKEND_SOURCE_BRANCH} -> staging"
promote_branch "${BACKEND_SOURCE}" "${BACKEND_STAGING}" "${BACKEND_SOURCE_BRANCH}" "staging" "backend"

echo "[sync-staging] Promoting frontend branch ${FRONTEND_SOURCE_BRANCH} -> staging"
promote_branch "${FRONTEND_SOURCE}" "${FRONTEND_STAGING}" "${FRONTEND_SOURCE_BRANCH}" "staging" "frontend"

touch "${BACKEND_STAGING}/.deploy-enabled"

echo "[sync-staging] Triggering staging deploy from remote branches"
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-staging.sh"
