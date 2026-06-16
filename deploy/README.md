# Plane Self-Hosted Deploy

Server vừa là **GitHub Actions runner** vừa là **Docker daemon** — build image local, không cần push Docker Hub.

## Kiến trúc

```
push develop → self-hosted runner (ns564701)
  ├── git checkout
  ├── docker compose build (6 images, tag plane-local/plane-*:<sha>)
  ├── docker compose up -d
  └── nginx reload
```

| Thành phần | Path trên server |
|------------|------------------|
| Source (runner checkout) | `~/actions-runner/_work/plane/plane` |
| Secrets / env | `/opt/plane/plane.env` (không commit) |
| Nginx config | `/etc/nginx/conf.d/plane.conf` |
| Data volumes | Docker volumes `plane_*` |

## Setup lần đầu (trên server)

### 1. SSH key GitHub (đã có)

```bash
ssh-add ~/.ssh/githubglu
git clone git@github.com:glu-developer-team/plane.git
```

### 2. Cài Docker (nếu chưa có)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
```

### 3. Tạo env từ deploy cũ (bita-plane)

Port biến từ `bita-plane/.env` → `/opt/plane/operator.env`:

```bash
sudo cp deploy/operator.env.example /opt/plane/operator.env
sudo vim /opt/plane/operator.env   # paste passwords/SMTP từ plane.env cũ
OPERATOR_ENV=/opt/plane/operator.env PLANE_ENV=/opt/plane/plane.env ./deploy/bin/generate-plane-env.sh
```

Biến map 1:1 từ deploy cũ:

| bita-plane `.env` | plane `operator.env` |
|-------------------|----------------------|
| `APP_DOMAIN`, `WEB_URL`, `CORS_*` | giữ nguyên |
| `NGINX_*`, `SSL_*`, `PLANE_UPSTREAM_*` | giữ nguyên |
| `USE_BUNDLED_DB/REDIS/MINIO` | giữ nguyên |
| `POSTGRES_*`, `RABBITMQ_*`, `AWS_*` | giữ nguyên |
| `ENABLE_SMTP`, `EMAIL_*` | giữ nguyên |
| `SECRET_KEY`, `LIVE_SERVER_SECRET_KEY` | paste từ plane.env cũ |

`generate-plane-env.sh` sinh `/opt/plane/plane.env` đúng format deploy cũ (`WEB_REPLICAS`, `TRUSTED_PROXIES`, `PGHOST`, ...).

### 4. Nginx + SSL

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
cd plane
PLANE_ENV=/opt/plane/plane.env ./deploy/bin/generate-nginx.sh
sudo cp deploy/nginx/plane.conf /etc/nginx/conf.d/plane.conf
sudo nginx -t && sudo systemctl reload nginx

# SSL lần đầu (tạm HTTP-only nếu chưa có cert)
sudo certbot certonly --nginx -d YOUR_DOMAIN --non-interactive --agree-tos -m admin@example.com
```

### 5. GitHub Actions self-hosted runner

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf actions-runner-linux-x64-2.321.0.tar.gz

# Lấy token tại: GitHub → glu-developer-team/plane → Settings → Actions → Runners → New
./config.sh --url https://github.com/glu-developer-team/plane --token <TOKEN> --name ns564701 --labels self-hosted,Linux,X64,plane

sudo ./svc.sh install ubuntu
sudo ./svc.sh start
```

Runner user `ubuntu` cần quyền:

```bash
sudo usermod -aG docker ubuntu
# Cho phép reload nginx không cần password (optional):
echo 'ubuntu ALL=(ALL) NOPASSWD: /usr/sbin/nginx, /bin/systemctl reload nginx, /bin/cp' | sudo tee /etc/sudoers.d/plane-deploy
```

### 6. Deploy thủ công (không qua CI)

```bash
cd plane
git checkout develop && git pull
PLANE_ENV=/opt/plane/plane.env ./deploy/bin/deploy.sh --nginx-reload
```

## Workflow tự động

File: `.github/workflows/deploy-self-hosted.yml`

- **Trigger:** push lên `develop`, hoặc manual `workflow_dispatch`
- **Build:** ~15–30 phút lần đầu, ~5–10 phút lần sau (Docker cache)
- **Tag image:** `plane-local/plane-frontend:<git-sha>`

Skip build (chỉ restart):

```bash
# GitHub UI → Actions → Deploy (self-hosted) → Run workflow → skip_build: true
```

## Custom code (Mermaid, v.v.)

1. Develop trên branch `feature/*` từ `develop`
2. Merge vào `develop` → CI tự build + deploy
3. Image chứa custom code được tag theo commit SHA

## Troubleshooting

```bash
# Xem logs
docker compose -f deploy/docker-compose.yml --env-file /opt/plane/plane.env logs -f api

# Trạng thái
docker compose -f deploy/docker-compose.yml --env-file /opt/plane/plane.env ps

# Dọn image cũ
docker image prune -f
```

## So sánh với pull upstream stable

| | `makeplane:stable` pull | Self-hosted build |
|--|-------------------------|-------------------|
| Custom code | Không | Có |
| Build time | Không | 15–30 phút |
| Registry | Docker Hub | Local only |
| Phù hợp | Chạy thử CE thuần | Fork + custom features |
