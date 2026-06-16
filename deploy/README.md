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

### 3. Tạo plane.env

```bash
sudo mkdir -p /opt/plane
sudo cp plane/deploy/plane.env.example /opt/plane/plane.env
sudo vim /opt/plane/plane.env   # điền domain, password, secret key
sudo chmod 600 /opt/plane/plane.env
```

Generate secrets:

```bash
openssl rand -hex 32   # SECRET_KEY
openssl rand -hex 32   # LIVE_SERVER_SECRET_KEY
```

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
