#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE="/tmp/video-processing-auto-deploy.lock"
exec 9>"${LOCK_FILE}"
flock -n 9 || exit 0

PROJECTS_ROOT="/home/vpsroot/projects"

BACKEND_SOURCE="${PROJECTS_ROOT}/backend/video-processing-service"
FRONTEND_SOURCE="${PROJECTS_ROOT}/frontend/video-processing-service-fe"
BACKEND_STAGING="${PROJECTS_ROOT}/backend/video-processing-service-staging"
BACKEND_PROD="${PROJECTS_ROOT}/backend/video-processing-service-prod"
FRONTEND_STAGING="${PROJECTS_ROOT}/frontend/video-processing-service-fe-staging"
FRONTEND_PROD="${PROJECTS_ROOT}/frontend/video-processing-service-fe-prod"

SETUP_SCRIPT="${BACKEND_SOURCE}/scripts/setup-deploy-worktrees.sh"
STAGING_DEPLOY_SCRIPT="${BACKEND_SOURCE}/scripts/deploy-staging.sh"
PROD_DEPLOY_SCRIPT="${BACKEND_SOURCE}/scripts/deploy-prod.sh"

"${SETUP_SCRIPT}"

git -C "${BACKEND_SOURCE}" fetch origin
git -C "${FRONTEND_SOURCE}" fetch origin || true

needs_update() {
  local source_repo="$1"
  local target_dir="$2"
  local branch_name="$3"

  if ! git -C "${source_repo}" show-ref --verify --quiet "refs/remotes/origin/${branch_name}"; then
    return 1
  fi

  local remote_sha
  local local_sha
  remote_sha="$(git -C "${source_repo}" rev-parse "origin/${branch_name}")"
  local_sha="$(git -C "${target_dir}" rev-parse HEAD)"

  [ "${remote_sha}" != "${local_sha}" ]
}

maybe_deploy() {
  local env_name="$1"
  local marker_file="$2"
  local deploy_script="$3"

  if [ ! -f "${marker_file}" ]; then
    return 0
  fi

  echo "[auto-deploy] Detected new ${env_name} commit"
  "${deploy_script}"
}

if needs_update "${BACKEND_SOURCE}" "${BACKEND_STAGING}" "staging" || needs_update "${FRONTEND_SOURCE}" "${FRONTEND_STAGING}" "staging"; then
  maybe_deploy "staging" "${BACKEND_STAGING}/.deploy-enabled" "${STAGING_DEPLOY_SCRIPT}"
fi

if needs_update "${BACKEND_SOURCE}" "${BACKEND_PROD}" "prod" || needs_update "${FRONTEND_SOURCE}" "${FRONTEND_PROD}" "prod"; then
  maybe_deploy "prod" "${BACKEND_PROD}/.deploy-enabled" "${PROD_DEPLOY_SCRIPT}"
fi
