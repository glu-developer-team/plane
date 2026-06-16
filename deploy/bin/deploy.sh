#!/usr/bin/env bash
# Self-hosted deploy: build Docker images locally + docker compose up
#
# Usage:
#   PLANE_ENV=/opt/plane/plane.env ./deploy/bin/deploy.sh
#   PLANE_ENV=/opt/plane/plane.env ./deploy/bin/deploy.sh --skip-build
#   PLANE_ENV=/opt/plane/plane.env ./deploy/bin/deploy.sh --nginx-reload

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${DEPLOY_DIR}/.." && pwd)"

PLANE_ENV="${PLANE_ENV:-/opt/plane/plane.env}"
DOCKERHUB_USER="${DOCKERHUB_USER:-plane-local}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-plane}"
SKIP_BUILD=false
NGINX_RELOAD=false
KEEP_IMAGE_TAGS="${KEEP_IMAGE_TAGS:-5}"

log()  { printf '\033[0;32m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[deploy]\033[0m %s\n' "$*"; }
die()  { printf '\033[0;31m[deploy]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Self-hosted Plane deploy

Options:
  --skip-build      Skip docker build (reuse existing local images)
  --nginx-reload    Reload nginx after deploy
  -h, --help        Show this help

Environment:
  PLANE_ENV         Path to plane.env (default: /opt/plane/plane.env)
  DOCKERHUB_USER    Local image namespace (default: plane-local)
  APP_RELEASE       Image tag (default: git short SHA)
  COMPOSE_PROJECT_NAME  Docker compose project name (default: plane)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build) SKIP_BUILD=true; shift ;;
    --nginx-reload) NGINX_RELOAD=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[[ -f "$PLANE_ENV" ]] || die "Missing plane.env at ${PLANE_ENV} — run generate-plane-env.sh or copy deploy/plane.env.example"

truthy() {
  local v
  v="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$v" in
    true|1|yes|y) return 0 ;;
    *) return 1 ;;
  esac
}

set -a
# shellcheck disable=SC1090
source "$PLANE_ENV"
set +a

# Self-hosted deploy always pins to current git commit (override plane.env APP_RELEASE=develop)
if git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  APP_RELEASE="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
else
  APP_RELEASE="${APP_RELEASE:-develop}"
fi

compose_file() {
  if ! truthy "${USE_BUNDLED_DB:-true}" || \
     ! truthy "${USE_BUNDLED_REDIS:-true}" || \
     ! truthy "${USE_BUNDLED_MINIO:-true}"; then
    printf '%s/docker-compose.external.yml' "$DEPLOY_DIR"
  fi
}

compose_args() {
  COMPOSE_ARGS=(-f "${DEPLOY_DIR}/docker-compose.yml")
  local external
  external="$(compose_file)"
  [[ -n "$external" ]] && COMPOSE_ARGS+=(-f "$external")
}

compose() {
  compose_args
  docker compose -p "$COMPOSE_PROJECT_NAME" "${COMPOSE_ARGS[@]}" --env-file "$PLANE_ENV" "$@"
}

compose_build() {
  compose_args
  docker compose -p "$COMPOSE_PROJECT_NAME" \
    "${COMPOSE_ARGS[@]}" \
    -f "${DEPLOY_DIR}/docker-compose.build.yml" \
    --env-file "$PLANE_ENV" \
    "$@"
}

export DOCKERHUB_USER APP_RELEASE COMPOSE_PROJECT_NAME

log "Release: ${DOCKERHUB_USER}/plane-*:${APP_RELEASE}"
log "Env file: ${PLANE_ENV}"

if [[ "$SKIP_BUILD" == "false" ]]; then
  log "Building images (this may take 15-30 minutes on first run)..."
  compose_build build --parallel
  log "Build complete"
else
  warn "Skipping build — using existing local images"
fi

log "Starting stack..."
compose up -d --remove-orphans

log "Waiting for API..."
for i in $(seq 1 30); do
  if compose ps api 2>/dev/null | grep -q "Up"; then
    break
  fi
  sleep 2
done

compose ps

# Prune old local plane images (keep last N tags)
if command -v docker >/dev/null 2>&1; then
  old_tags=$(
    docker images "${DOCKERHUB_USER}/plane-frontend" --format '{{.Tag}}' 2>/dev/null \
      | grep -vE '^<none>$|^${APP_RELEASE}$' \
      | tail -n +$((KEEP_IMAGE_TAGS + 1)) || true
  )
  if [[ -n "$old_tags" ]]; then
    warn "Pruning old image tags..."
    while IFS= read -r tag; do
      [[ -z "$tag" || "$tag" == "$APP_RELEASE" ]] && continue
      for svc in plane-frontend plane-space plane-admin plane-live plane-backend plane-proxy; do
        docker rmi "${DOCKERHUB_USER}/${svc}:${tag}" 2>/dev/null || true
      done
    done <<< "$old_tags"
  fi
fi

if [[ "$NGINX_RELOAD" == "true" ]]; then
  if ! truthy "${USE_NGINX_PROXY:-true}"; then
    warn "USE_NGINX_PROXY=false — skipping nginx reload"
  elif [[ -f "${DEPLOY_DIR}/nginx/plane.conf" ]]; then
    NGINX_CONF="${NGINX_CONF_PATH:-/etc/nginx/conf.d/plane.conf}"
    log "Deploying nginx config → ${NGINX_CONF}"
    sudo cp "${DEPLOY_DIR}/nginx/plane.conf" "$NGINX_CONF"
    sudo nginx -t
    sudo systemctl reload nginx
    log "Nginx reloaded"
  else
    warn "No deploy/nginx/plane.conf — run deploy/bin/generate-nginx.sh first"
  fi
fi

log "Deploy complete — APP_RELEASE=${APP_RELEASE}"
