#!/usr/bin/env bash
set -euo pipefail

TARGET_CONF="/www/server/panel/vhost/nginx/test.plxeditor.com.conf"

cat <<'EOF' >/tmp/test.plxeditor.com.conf
server
{
    listen 80;
    server_name test.plxeditor.com;

    location / {
        proxy_pass http://127.0.0.1:3010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
EOF

sudo cp /tmp/test.plxeditor.com.conf "${TARGET_CONF}"
sudo nginx -t
sudo nginx -s reload

echo "[host-nginx] Installed ${TARGET_CONF}"
