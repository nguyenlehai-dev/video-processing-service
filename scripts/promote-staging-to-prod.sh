#!/usr/bin/env bash
set -euo pipefail

PROJECTS_ROOT="/home/vpsroot/projects"

BACKEND_SOURCE="${PROJECTS_ROOT}/backend/video-processing-service"
FRONTEND_SOURCE="${PROJECTS_ROOT}/frontend/video-processing-service-fe"
BACKEND_PROD="${PROJECTS_ROOT}/backend/video-processing-service-prod"
BACKEND_STAGING="${PROJECTS_ROOT}/backend/video-processing-service-staging"
FRONTEND_STAGING="${PROJECTS_ROOT}/frontend/video-processing-service-fe-staging"
FRONTEND_PROD="${PROJECTS_ROOT}/frontend/video-processing-service-fe-prod"

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
  echo "[promote-prod] ${label}: ${source_branch} -> ${target_branch} pushed"
}

echo "[promote-prod] Promoting backend staging -> prod"
promote_branch "${BACKEND_SOURCE}" "${BACKEND_PROD}" "staging" "prod" "backend"

echo "[promote-prod] Promoting frontend staging -> prod"
promote_branch "${FRONTEND_SOURCE}" "${FRONTEND_PROD}" "staging" "prod" "frontend"

touch "${BACKEND_PROD}/.deploy-enabled"

echo "[promote-prod] Triggering production deploy from remote branches"
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-prod.sh"
