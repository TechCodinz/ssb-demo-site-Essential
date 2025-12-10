#!/bin/bash
# ============================================
# SSB PRO Cloud - Deploy Application
# Run this after uploading code to /var/www/ssb-cloud-api
# ============================================

set -e

APP_DIR="/var/www/ssb-cloud-api"

echo "🚀 Deploying SSB PRO Cloud API..."

cd $APP_DIR

# ====== STEP 1: CREATE VIRTUAL ENVIRONMENT ======
echo "🐍 Setting up Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# ====== STEP 2: INSTALL DEPENDENCIES ======
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install \
    fastapi[all] \
    uvicorn[standard] \
    pyjwt \
    python-multipart \
    psycopg2-binary \
    sqlalchemy \
    alembic \
    asyncpg \
    python-dotenv \
    httpx \
    aiofiles \
    passlib[bcrypt] \
    python-telegram-bot \
    docker

# ====== STEP 3: CREATE .ENV FILE ======
echo "⚙️ Creating environment file..."
cat > .env << 'EOF'
# SSB PRO Cloud API - Environment Variables

# App
APP_NAME=SSB PRO Cloud API
DEBUG=False
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql://ssbadmin:SSBCloud2025DB!@localhost:5432/ssb_cloud

# JWT
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# SMTP (configure with your provider)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@ssbpro.dev

# USDT Payment
USDT_WALLET=TBxck6t1a3pZE2YLho4Su1PcGKd2yK2zD4
USDT_NETWORK=TRC20

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
ADMIN_CHAT_ID=your-admin-chat-id

# Admin
ADMIN_PASSWORD=SSBCloud2025Admin!
EOF

echo "⚠️ IMPORTANT: Edit .env file with your actual secrets!"

# ====== STEP 4: SETUP PM2 PROCESS ======
echo "🔧 Setting up PM2 process manager..."

cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'ssb-api',
      script: 'venv/bin/uvicorn',
      args: 'api.main:app --host 0.0.0.0 --port 8000',
      cwd: '/var/www/ssb-cloud-api',
      interpreter: 'none',
      env: {
        NODE_ENV: 'production'
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      log_file: '/var/www/ssb-cloud-api/logs/api.log',
      error_file: '/var/www/ssb-cloud-api/logs/api-error.log',
      out_file: '/var/www/ssb-cloud-api/logs/api-out.log'
    },
    {
      name: 'ssb-license',
      script: 'venv/bin/uvicorn',
      args: 'license_server.main:app --host 0.0.0.0 --port 8001',
      cwd: '/var/www/ssb-cloud-api',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      log_file: '/var/www/ssb-cloud-api/logs/license.log'
    },
    {
      name: 'ssb-engine',
      script: 'venv/bin/uvicorn',
      args: 'cloud_engine.main:app --host 0.0.0.0 --port 8002',
      cwd: '/var/www/ssb-cloud-api',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      log_file: '/var/www/ssb-cloud-api/logs/engine.log'
    },
    {
      name: 'ssb-telegram-bot',
      script: 'venv/bin/python',
      args: 'telegram_bot/bot.py',
      cwd: '/var/www/ssb-cloud-api',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      log_file: '/var/www/ssb-cloud-api/logs/telegram.log'
    }
  ]
};
EOF

# ====== STEP 5: START SERVICES ======
echo "🚀 Starting services with PM2..."
pm2 start ecosystem.config.js
pm2 save
pm2 startup

echo ""
echo "✅ Deployment Complete!"
echo ""
echo "Services running:"
pm2 list
echo ""
echo "API: http://localhost:8000/docs"
echo "Health: http://localhost:8000/health"
