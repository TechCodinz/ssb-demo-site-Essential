#!/bin/bash
# ====== NGINX CONFIGURATION FOR SSBPRO.DEV ======

echo "Configuring Nginx for ssbpro.dev..."

cat > /etc/nginx/sites-available/ssbpro << 'EOF'
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# Main site - ssbpro.dev
server {
    listen 80;
    server_name ssbpro.dev www.ssbpro.dev;

    location / {
        proxy_pass https://ssb-demo-site-essential.vercel.app;
        proxy_set_header Host ssb-demo-site-essential.vercel.app;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_ssl_verify off;
    }
}

# API - api.ssbpro.dev
server {
    listen 80;
    server_name api.ssbpro.dev;

    location / {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}

# License - license.ssbpro.dev
server {
    listen 80;
    server_name license.ssbpro.dev;

    location / {
        limit_req zone=api_limit burst=10 nodelay;
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Engine - engine.ssbpro.dev  
server {
    listen 80;
    server_name engine.ssbpro.dev;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}

# Download - download.ssbpro.dev
server {
    listen 80;
    server_name download.ssbpro.dev;

    root /var/www/ssb-releases;

    valid_referers none blocked ssbpro.dev *.ssbpro.dev;
    if ($invalid_referer) {
        return 403;
    }

    location / {
        limit_rate 1m;
        try_files $uri $uri/ =404;
    }
}

# Admin - admin.ssbpro.dev
server {
    listen 80;
    server_name admin.ssbpro.dev;

    location / {
        proxy_pass http://127.0.0.1:8003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Orders webhook - orders.ssbpro.dev
server {
    listen 80;
    server_name orders.ssbpro.dev;

    location / {
        proxy_pass http://127.0.0.1:8004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/ssbpro /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload
nginx -t && systemctl reload nginx

echo ""
echo "✅ Nginx configured for all subdomains!"
echo ""
echo "Now add these DNS records at Namecheap:"
echo "=========================================="
echo "Type  | Host      | Value"
echo "------|-----------|----------------"
echo "A     | @         | 194.163.151.208"
echo "A     | api       | 194.163.151.208"
echo "A     | license   | 194.163.151.208"
echo "A     | engine    | 194.163.151.208"
echo "A     | download  | 194.163.151.208"
echo "A     | admin     | 194.163.151.208"
echo "A     | orders    | 194.163.151.208"
echo "CNAME | www       | ssbpro.dev."
echo ""
echo "After DNS propagates (5-30 min), run:"
echo "certbot --nginx -d ssbpro.dev -d www.ssbpro.dev -d api.ssbpro.dev -d license.ssbpro.dev -d engine.ssbpro.dev -d download.ssbpro.dev -d admin.ssbpro.dev -d orders.ssbpro.dev"
