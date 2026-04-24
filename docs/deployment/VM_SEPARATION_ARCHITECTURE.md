# Video Processing VM Separation Architecture

## Muc tieu

Tach rieng `staging` va `prod` thanh 2 Ubuntu VM doc lap:

- `VM dev` chi chay `video-processing-staging`
- `VM pro` chi chay `video-processing-prod`
- public ingress va Cloudflare Tunnel tap trung tai `VM pro`

## Hien trang thuc te

### VM dev

Hostname: `dev`  
IP noi bo: `192.168.100.67`

Runtime dang chay:

- Backend: `/home/vpsroot/apps/video-processing-staging/be`
- Frontend: `/home/vpsroot/apps/video-processing-staging/fe`
- Domain: `test.plxeditor.com`

Ports:

- `18082` -> Video backend staging
- `8081` -> Video frontend staging

Runner:

- `video-be-dev`
- `video-fe-dev`

Cloudflared:

- khong can public tunnel rieng tren `VM dev`
- traffic public `test.plxeditor.com` di qua `VM pro`

### VM pro

Hostname: `pro`  
IP noi bo: `192.168.100.68`

Runtime dang chay:

- Backend: `/home/vpsroot/apps/video-processing-prod/be`
- Frontend: `/home/vpsroot/apps/video-processing-prod/fe`
- Domain: `plxeditor.com`

Ports:

- `28081` -> Video backend prod
- `28082` -> Video frontend prod

Runner:

- `video-be-prod`
- `video-fe-prod`

Cloudflared:

- chay bang `systemd`
- service: `cloudflared.service`

## Domain routing

Public domains:

- `test.plxeditor.com`
- `plxeditor.com`

Current ingress model:

- Cloudflare/Cloudflared vao `VM pro`
- Nginx Proxy Manager tren `VM pro` route:
  - `test.plxeditor.com` -> `192.168.100.67:8081`
  - `plxeditor.com` -> `192.168.100.68:28082`

## Source va runtime

Source repos:

- `/home/vpsroot/projects/backend/video-processing-service`
- `/home/vpsroot/projects/frontend/video-processing-service-fe`

Runtime deploy:

- `/home/vpsroot/apps/video-processing-staging`
- `/home/vpsroot/apps/video-processing-prod`

Git flow:

- `staging` deploy vao `VM dev`
- `prod` deploy vao `VM pro`

## Van hanh chuan

1. Lam viec va push branch `staging`
2. Verify `https://test.plxeditor.com/`
3. Promote `staging -> prod`
4. Verify `https://plxeditor.com/`

## Health checks nhanh

### VM dev

```bash
docker ps
curl -s http://127.0.0.1:18082/health
curl -I -s https://test.plxeditor.com/
systemctl list-units --type=service --all | egrep 'video|runner'
```

### VM pro

```bash
docker ps
curl -s http://127.0.0.1:28081/health
curl -I -s https://plxeditor.com/
systemctl status cloudflared --no-pager
```
