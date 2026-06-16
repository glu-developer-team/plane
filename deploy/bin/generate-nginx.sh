#!/usr/bin/env bash
# Generate nginx/plane.conf from plane.env values
#
# Usage:
#   PLANE_ENV=/opt/plane/plane.env ./deploy/bin/generate-nginx.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLANE_ENV="${PLANE_ENV:-/opt/plane/plane.env}"
OUT="${DEPLOY_DIR}/nginx/plane.conf"

[[ -f "$PLANE_ENV" ]] || { echo "Missing ${PLANE_ENV}" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
source "$PLANE_ENV"
set +a

APP_DOMAIN="${APP_DOMAIN:-localhost}"
PLANE_UPSTREAM_HOST="${PLANE_UPSTREAM_HOST:-127.0.0.1}"
PLANE_UPSTREAM_PORT="${PLANE_UPSTREAM_PORT:-8080}"
NGINX_HTTP_PORT="${NGINX_HTTP_PORT:-80}"
NGINX_HTTPS_PORT="${NGINX_HTTPS_PORT:-443}"
FILE_SIZE_LIMIT="${FILE_SIZE_LIMIT:-5242880}"
NGINX_SSL_ENABLED="${NGINX_SSL_ENABLED:-true}"
SSL_CERT_PATH="${SSL_CERT_PATH:-/etc/letsencrypt/live/${APP_DOMAIN}/fullchain.pem}"
SSL_KEY_PATH="${SSL_KEY_PATH:-/etc/letsencrypt/live/${APP_DOMAIN}/privkey.pem}"

mkdir -p "${DEPLOY_DIR}/nginx"

PROXY_BLOCK='        proxy_pass http://plane_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;'

{
  cat <<'EOF'
# Plane CE — Nginx reverse proxy (generated)

map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

EOF
  printf 'upstream plane_app {\n    server %s:%s;\n    keepalive 32;\n}\n\n' \
    "$PLANE_UPSTREAM_HOST" "$PLANE_UPSTREAM_PORT"

  if [[ "${NGINX_SSL_ENABLED}" == "true" ]]; then
    cat <<EOF
server {
    listen ${NGINX_HTTP_PORT};
    listen [::]:${NGINX_HTTP_PORT};
    server_name ${APP_DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen ${NGINX_HTTPS_PORT} ssl http2;
    listen [::]:${NGINX_HTTPS_PORT} ssl http2;
    server_name ${APP_DOMAIN};

    ssl_certificate ${SSL_CERT_PATH};
    ssl_certificate_key ${SSL_KEY_PATH};
    ssl_session_timeout 1d;
    ssl_session_cache shared:PlaneSSL:10m;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size ${FILE_SIZE_LIMIT};

    location / {
${PROXY_BLOCK}
    }
}
EOF
  else
    cat <<EOF
server {
    listen ${NGINX_HTTP_PORT};
    listen [::]:${NGINX_HTTP_PORT};
    server_name ${APP_DOMAIN};

    client_max_body_size ${FILE_SIZE_LIMIT};

    location / {
${PROXY_BLOCK}
    }
}
EOF
  fi
} >"$OUT"

echo "Generated ${OUT}"
