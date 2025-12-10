#!/bin/bash
# ============================================
# SSB PRO Cloud - VPS Setup Script (Part 3)
# Nginx, SSL, and Application Deployment
# ============================================

set -e

echo "🚀 SSB PRO Cloud - Part 3: Nginx & Deployment..."

# ====== STEP 1: CONFIGURE NGINX ======
echo "🌐 Configuring Nginx..."

cat > /etc/nginx/sites-available/ssbpro << 'EOF'
# SSB PRO Cloud - Nginx Configuration

# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# Main site - ssbpro.dev
server {
    listen 80;
    server_name ssbpro.dev www.ssbpro.dev;

    # Redirect to HTTPS (uncomment after SSL setup)
    # return 301 https://$server_name$request_uri;

    location / {
        # Proxy to Vercel (or serve static files)
        proxy_pass https://ssb-demo-site-essential.vercel.app;
        proxy_set_header Host ssb-demo-site-essential.vercel.app;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_ssl_verify off;
    }
}

# API Server - api.ssbpro.dev
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
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}

# License Server - license.ssbpro.dev
server {
    listen 80;
    server_name license.ssbpro.dev;

    location / {
        limit_req zone=api_limit burst=10 nodelay;
        
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# Cloud Engine - engine.ssbpro.dev
server {
    listen 80;
    server_name engine.ssbpro.dev;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
    
    # WebSocket for live logs
    location /ws {
        proxy_pass http://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}

# Download Server - download.ssbpro.dev
server {
    listen 80;
    server_name download.ssbpro.dev;

    root /var/www/ssb-releases;
    
    # Anti-hotlinking
    valid_referers none blocked ssbpro.dev *.ssbpro.dev;
    if ($invalid_referer) {
        return 403;
    }
    
    # Rate limit downloads
    location / {
        limit_rate 1m;  # 1MB/s per connection
        try_files $uri $uri/ =404;
    }
}

# Admin Panel - admin.ssbpro.dev
server {
    listen 80;
    server_name admin.ssbpro.dev;

    location / {
        proxy_pass http://127.0.0.1:8003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Orders Webhook - orders.ssbpro.dev
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

# Test and reload nginx
nginx -t
systemctl reload nginx

echo "✅ Nginx configured!"

# ====== STEP 2: SETUP SSL WITH CERTBOT ======
echo "🔒 Setting up SSL certificates..."
echo ""
echo "Run this command to get SSL certificates:"
echo ""
echo "certbot --nginx -d ssbpro.dev -d www.ssbpro.dev -d api.ssbpro.dev -d license.ssbpro.dev -d engine.ssbpro.dev -d download.ssbpro.dev -d admin.ssbpro.dev -d orders.ssbpro.dev"
echo ""

# ====== STEP 3: SETUP AUTO-RENEWAL ======
echo "Setting up SSL auto-renewal..."
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -

echo "✅ Part 3 Complete!"
echo ""
echo "Manual steps remaining:"
echo "1. Add DNS records at your domain registrar"
echo "2. Run certbot command above for SSL"
echo "3. Deploy the application code"
