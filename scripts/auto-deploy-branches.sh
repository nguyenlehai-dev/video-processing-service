#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE="/tmp/video-processing-auto-deploy.lock"
exec 9>"${LOCK_FILE}"
flock -n 9 || exit 0

PROJECTS_ROOT="/home/vpsroot/projects"

BACKEND_SOURCE="${PROJECTS_ROOT}/backend/video-processing-service"
FRONTEND_SOURCE="${PROJECTS_ROOT}/frontend/video-processing-service-fe"
DEPLOY_ROOT="${BACKEND_SOURCE}/deploy"
STAGING_DEPLOY_SCRIPT="${BACKEND_SOURCE}/scripts/deploy-image-staging.sh"
PROD_DEPLOY_SCRIPT="${BACKEND_SOURCE}/scripts/deploy-image-prod.sh"
STAGING_BACKEND_SHA_FILE="${DEPLOY_ROOT}/staging/backend.sha"
STAGING_FRONTEND_SHA_FILE="${DEPLOY_ROOT}/staging/frontend.sha"
PROD_BACKEND_SHA_FILE="${DEPLOY_ROOT}/prod/backend.sha"
PROD_FRONTEND_SHA_FILE="${DEPLOY_ROOT}/prod/frontend.sha"

git -C "${BACKEND_SOURCE}" fetch origin
git -C "${FRONTEND_SOURCE}" fetch origin || true

needs_update() {
  local source_repo="$1"
  local branch_name="$3"
  local deployed_sha_file="$4"

  if ! git -C "${source_repo}" show-ref --verify --quiet "refs/remotes/origin/${branch_name}"; then
    return 1
  fi

  local remote_sha
  remote_sha="$(git -C "${source_repo}" rev-parse "origin/${branch_name}")"
  local deployed_sha=""
  if [ -f "${deployed_sha_file}" ]; then
    deployed_sha="$(tr -d '\n' < "${deployed_sha_file}")"
  fi

  [ "${remote_sha}" != "${deployed_sha}" ]
}

maybe_deploy() {
  local env_name="$1"
  local deploy_script="$2"

  echo "[auto-deploy] Detected new ${env_name} commit"
  "${deploy_script}"
}

if needs_update "${BACKEND_SOURCE}" "staging" "${STAGING_BACKEND_SHA_FILE}" || needs_update "${FRONTEND_SOURCE}" "staging" "${STAGING_FRONTEND_SHA_FILE}"; then
  maybe_deploy "staging" "${STAGING_DEPLOY_SCRIPT}"
fi

if needs_update "${BACKEND_SOURCE}" "prod" "${PROD_BACKEND_SHA_FILE}" || needs_update "${FRONTEND_SOURCE}" "prod" "${PROD_FRONTEND_SHA_FILE}"; then
  maybe_deploy "prod" "${PROD_DEPLOY_SCRIPT}"
fi
