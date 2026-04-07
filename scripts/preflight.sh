#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

fail() {
  echo "[preflight] ERROR: $1" >&2
  exit 1
}

warn() {
  echo "[preflight] WARN: $1" >&2
}

info() {
  echo "[preflight] INFO: $1"
}

[[ -f "${ENV_FILE}" ]] || fail "Missing .env file at ${ENV_FILE}"

get_env_value() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 || true)"
  echo "${line#*=}"
}

require_non_placeholder() {
  local key="$1"
  local value
  value="$(get_env_value "${key}")"

  if [[ -z "${value}" ]]; then
    fail "Missing required env var: ${key}"
  fi

  case "${value}" in
    your-*|change-this-*|https://pub-xxx.r2.dev|eyJhIjoixxxxxxxxx...your-actual-token-here)
      fail "Env var ${key} is still using a placeholder value"
      ;;
  esac
}

storage_backend="$(get_env_value "STORAGE_BACKEND")"
storage_backend="${storage_backend:-auto}"

if [[ "${storage_backend}" == "r2" ]]; then
  info "Checking Cloudflare R2 configuration"
  require_non_placeholder "R2_ACCOUNT_ID"
  require_non_placeholder "R2_ACCESS_KEY_ID"
  require_non_placeholder "R2_SECRET_ACCESS_KEY"
  require_non_placeholder "R2_BUCKET_NAME"
  require_non_placeholder "R2_PUBLIC_URL"
else
  warn "STORAGE_BACKEND=${storage_backend}. Production should normally use STORAGE_BACKEND=r2"
fi

tunnel_token="$(get_env_value "CLOUDFLARE_TUNNEL_TOKEN")"
if [[ -z "${tunnel_token}" || "${tunnel_token}" == "your-tunnel-token" ]]; then
  warn "Cloudflare Tunnel token is missing or still placeholder"
fi

secret_key="$(get_env_value "SECRET_KEY")"
if [[ -z "${secret_key}" || "${secret_key}" == "change-this-to-a-random-secret-key" ]]; then
  fail "SECRET_KEY is missing or still placeholder"
fi

info "Validating docker-compose configuration"
(
  cd "${ROOT_DIR}"
  docker compose config >/dev/null
)

if docker info >/dev/null 2>&1; then
  info "Docker daemon is accessible"
else
  warn "Docker daemon is not accessible for the current user"
  warn "Fix by adding ${USER} to the docker group or run deploy commands with sudo"
fi

info "Preflight checks completed"
