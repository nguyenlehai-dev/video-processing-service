#!/usr/bin/env bash
set -euo pipefail

PROJECTS_ROOT="/home/vpsroot/projects"

BACKEND_SOURCE="${PROJECTS_ROOT}/backend/video-processing-service"
BACKEND_STAGING="${PROJECTS_ROOT}/backend/video-processing-service-staging"
BACKEND_PROD="${PROJECTS_ROOT}/backend/video-processing-service-prod"

FRONTEND_SOURCE="${PROJECTS_ROOT}/frontend/video-processing-service-fe"
FRONTEND_STAGING="${PROJECTS_ROOT}/frontend/video-processing-service-fe-staging"
FRONTEND_PROD="${PROJECTS_ROOT}/frontend/video-processing-service-fe-prod"

ensure_worktree() {
  local source_repo="$1"
  local target_dir="$2"
  local branch_name="$3"
  local remote_ref="$4"

  if [ -d "${target_dir}/.git" ] || [ -f "${target_dir}/.git" ]; then
    echo "[worktree] Exists: ${target_dir}"
    return
  fi

  if ! git -C "${source_repo}" show-ref --verify --quiet "refs/remotes/${remote_ref}"; then
    echo "[worktree] Missing remote branch ${remote_ref} for ${target_dir}" >&2
    exit 1
  fi

  echo "[worktree] Creating ${branch_name} at ${target_dir}"
  git -C "${source_repo}" worktree add -B "${branch_name}" "${target_dir}" "${remote_ref}"
}

git -C "${BACKEND_SOURCE}" fetch origin
git -C "${FRONTEND_SOURCE}" fetch origin || true

ensure_worktree "${BACKEND_SOURCE}" "${BACKEND_STAGING}" "staging" "origin/staging"
ensure_worktree "${BACKEND_SOURCE}" "${BACKEND_PROD}" "prod" "origin/prod"
ensure_worktree "${FRONTEND_SOURCE}" "${FRONTEND_STAGING}" "staging" "origin/staging"
ensure_worktree "${FRONTEND_SOURCE}" "${FRONTEND_PROD}" "prod" "origin/prod"

echo "[worktree] Ready"
