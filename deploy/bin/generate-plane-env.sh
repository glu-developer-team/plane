#!/usr/bin/env bash
# Generate plane.env from operator.env (port từ bita-plane/scripts/lib.sh)
#
# Usage:
#   OPERATOR_ENV=/opt/plane/operator.env PLANE_ENV=/opt/plane/plane.env ./deploy/bin/generate-plane-env.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

OPERATOR_ENV="${OPERATOR_ENV:-/opt/plane/operator.env}"
PLANE_ENV="${PLANE_ENV:-/opt/plane/plane.env}"

log() { printf '\033[0;32m[generate-plane-env]\033[0m %s\n' "$*"; }
die() { printf '\033[0;31m[generate-plane-env]\033[0m %s\n' "$*" >&2; exit 1; }

truthy() {
  local v
  v="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$v" in
    true|1|yes|y) return 0 ;;
    *) return 1 ;;
  esac
}

env_quote() {
  local v="$1"
  v="${v//\\/\\\\}"
  v="${v//\"/\\\"}"
  printf '"%s"' "$v"
}

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    tr -dc 'a-zA-Z0-9' </dev/urandom | head -c 50
  fi
}

[[ -f "$OPERATOR_ENV" ]] || die "Missing ${OPERATOR_ENV} — cp deploy/operator.env.example ${OPERATOR_ENV}"

set -a
# shellcheck disable=SC1090
source "$OPERATOR_ENV"
set +a

local_db_url="" pg_host="" redis_url="" use_minio=""

if truthy "${USE_BUNDLED_DB:-true}"; then
  pg_host="plane-db"
  local_db_url="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@plane-db:${POSTGRES_PORT:-5432}/${POSTGRES_DB}"
else
  pg_host="${POSTGRES_HOST:-}"
  local_db_url="${EXTERNAL_DATABASE_URL:-}"
  [[ -n "$local_db_url" ]] || die "USE_BUNDLED_DB=false cần EXTERNAL_DATABASE_URL"
fi

if truthy "${USE_BUNDLED_REDIS:-true}"; then
  redis_url="redis://plane-redis:${REDIS_PORT:-6379}/"
else
  redis_url="${EXTERNAL_REDIS_URL:-}"
  [[ -n "$redis_url" ]] || die "USE_BUNDLED_REDIS=false cần EXTERNAL_REDIS_URL"
  REDIS_HOST="${REDIS_HOST:-$(echo "$redis_url" | sed -E 's|redis://([^:/]+).*|\1|')}"
fi

if truthy "${USE_BUNDLED_MINIO:-true}"; then
  use_minio=1
else
  use_minio=0
fi

secret_key="${SECRET_KEY:-}"
live_secret="${LIVE_SERVER_SECRET_KEY:-}"
[[ -n "$secret_key" ]] || secret_key="$(random_secret)"
[[ -n "$live_secret" ]] || live_secret="$(random_secret)"

q_db_pass="$(env_quote "${POSTGRES_PASSWORD}")"
q_rmq_pass="$(env_quote "${RABBITMQ_PASSWORD}")"
q_secret="$(env_quote "${secret_key}")"
q_live="$(env_quote "${live_secret}")"
q_aws_secret="$(env_quote "${AWS_SECRET_ACCESS_KEY}")"
q_db_url="$(env_quote "${local_db_url}")"
q_amqp_url="$(env_quote "amqp://${RABBITMQ_USER:-plane}:${RABBITMQ_PASSWORD}@plane-mq:5672/${RABBITMQ_VHOST:-plane}")"

mkdir -p "$(dirname "$PLANE_ENV")"

cat >"$PLANE_ENV" <<EOF
# Generated from ${OPERATOR_ENV} — do not edit by hand; re-run generate-plane-env.sh

APP_DOMAIN=${APP_DOMAIN}
DOCKERHUB_USER=${DOCKERHUB_USER:-plane-local}
APP_RELEASE=${APP_RELEASE:-develop}

USE_BUNDLED_DB=${USE_BUNDLED_DB:-true}
USE_BUNDLED_REDIS=${USE_BUNDLED_REDIS:-true}
USE_BUNDLED_MINIO=${USE_BUNDLED_MINIO:-true}

USE_NGINX_PROXY=${USE_NGINX_PROXY:-true}
NGINX_CONF_PATH=${NGINX_CONF_PATH:-/etc/nginx/conf.d/plane.conf}
NGINX_HTTP_PORT=${NGINX_HTTP_PORT:-80}
NGINX_HTTPS_PORT=${NGINX_HTTPS_PORT:-443}
PLANE_UPSTREAM_HOST=${PLANE_UPSTREAM_HOST:-127.0.0.1}
PLANE_UPSTREAM_PORT=${PLANE_UPSTREAM_PORT:-8080}
NGINX_SSL_ENABLED=${NGINX_SSL_ENABLED:-true}
SSL_CERT_PATH=${SSL_CERT_PATH:-/etc/letsencrypt/live/${APP_DOMAIN}/fullchain.pem}
SSL_KEY_PATH=${SSL_KEY_PATH:-/etc/letsencrypt/live/${APP_DOMAIN}/privkey.pem}
CERT_EMAIL=${CERT_EMAIL:-}

WEB_REPLICAS=1
SPACE_REPLICAS=1
ADMIN_REPLICAS=1
API_REPLICAS=1
WORKER_REPLICAS=1
BEAT_WORKER_REPLICAS=1
LIVE_REPLICAS=1

LISTEN_HTTP_PORT=${LISTEN_HTTP_PORT:-80}
LISTEN_HTTPS_PORT=${LISTEN_HTTPS_PORT:-443}

WEB_URL=${WEB_URL}
DEBUG=${DEBUG:-0}
CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS:-$WEB_URL}
API_BASE_URL=http://api:8000

PGHOST=${pg_host}
PGDATABASE=${POSTGRES_DB:-plane}
POSTGRES_USER=${POSTGRES_USER:-plane}
POSTGRES_PASSWORD=${q_db_pass}
POSTGRES_DB=${POSTGRES_DB:-plane}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
PGDATA=/var/lib/postgresql/data
DATABASE_URL=${q_db_url}

REDIS_HOST=${REDIS_HOST:-plane-redis}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_URL=${redis_url}

RABBITMQ_HOST=plane-mq
RABBITMQ_PORT=5672
RABBITMQ_USER=${RABBITMQ_USER:-plane}
RABBITMQ_PASSWORD=${q_rmq_pass}
RABBITMQ_VHOST=${RABBITMQ_VHOST:-plane}
AMQP_URL=${q_amqp_url}

CERT_ACME_CA=https://acme-v02.api.letsencrypt.org/directory
TRUSTED_PROXIES=0.0.0.0/0
SITE_ADDRESS=:80
CERT_ACME_DNS=

SECRET_KEY=${q_secret}
LIVE_SERVER_SECRET_KEY=${q_live}

USE_MINIO=${use_minio}
AWS_REGION=${AWS_REGION:-}
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-access-key}
AWS_SECRET_ACCESS_KEY=${q_aws_secret}
AWS_S3_ENDPOINT_URL=${AWS_S3_ENDPOINT_URL:-http://plane-minio:9000}
AWS_S3_BUCKET_NAME=${AWS_S3_BUCKET_NAME:-uploads}
FILE_SIZE_LIMIT=${FILE_SIZE_LIMIT:-5242880}

GUNICORN_WORKERS=${GUNICORN_WORKERS:-1}
MINIO_ENDPOINT_SSL=${MINIO_ENDPOINT_SSL:-0}
API_KEY_RATE_LIMIT=${API_KEY_RATE_LIMIT:-6000/minute}

WEBHOOK_ALLOWED_IPS=
WEBHOOK_ALLOWED_HOSTS=
EOF

if truthy "${ENABLE_SMTP:-false}" && [[ -n "${EMAIL_HOST:-}" ]]; then
  q_email_user="$(env_quote "${EMAIL_HOST_USER}")"
  q_email_pass="$(env_quote "${EMAIL_HOST_PASSWORD}")"
  q_email_from="$(env_quote "${EMAIL_FROM}")"
  cat >>"$PLANE_ENV" <<EOF

EMAIL_HOST=${EMAIL_HOST}
EMAIL_PORT=${EMAIL_PORT:-587}
EMAIL_USE_TLS=${EMAIL_USE_TLS:-1}
EMAIL_USE_SSL=${EMAIL_USE_SSL:-0}
EMAIL_HOST_USER=${q_email_user}
EMAIL_HOST_PASSWORD=${q_email_pass}
EMAIL_FROM=${q_email_from}
SKIP_ENV_VAR=${SKIP_ENV_VAR:-0}
EOF
fi

chmod 600 "$PLANE_ENV" 2>/dev/null || true
log "Generated ${PLANE_ENV}"
