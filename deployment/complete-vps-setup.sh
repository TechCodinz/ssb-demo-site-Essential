#!/bin/bash
# ============================================
# SSB PRO Cloud - COMPLETE VPS SETUP
# Server: 194.163.151.208
# Domain: ssbpro.dev
# 
# Run this ENTIRE script after SSH login:
# ssh root@194.163.151.208
# (password: NGk3QY79ctTFDtI4JkIZ5Bpdn)
# ============================================

set -e
export DEBIAN_FRONTEND=noninteractive

echo "========================================"
echo "🚀 SSB PRO Cloud - Complete VPS Setup"
echo "========================================"

# ====== SYSTEM UPDATE ======
echo "[1/12] Updating system..."
apt update && apt upgrade -y

# ====== BASE PACKAGES ======
echo "[2/12] Installing base packages..."
apt install -y curl wget git vim htop unzip software-properties-common \
    apt-transport-https ca-certificates gnupg lsb-release build-essential

# ====== PYTHON 3.11 ======
echo "[3/12] Installing Python 3.11..."
add-apt-repository ppa:deadsnakes/ppa -y
apt update
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
python3 --version

# ====== NODE.JS 18 + PM2 ======
echo "[4/12] Installing Node.js 18..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs
npm install -g pm2
node --version

# ====== POSTGRESQL ======
echo "[5/12] Installing PostgreSQL..."
apt install -y postgresql postgresql-contrib
systemctl start postgresql
systemctl enable postgresql

# ====== NGINX ======
echo "[6/12] Installing Nginx..."
apt install -y nginx
systemctl start nginx
systemctl enable nginx

# ====== DOCKER ======
echo "[7/12] Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh
systemctl start docker
systemctl enable docker

# ====== FAIL2BAN ======
echo "[8/12] Installing Fail2Ban..."
apt install -y fail2ban
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400
EOF
systemctl restart fail2ban
systemctl enable fail2ban

# ====== UFW FIREWALL ======
echo "[9/12] Configuring UFW Firewall..."
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable
ufw status

# ====== CREATE SSBADMIN USER ======
echo "[10/12] Creating ssbadmin user..."
useradd -m -s /bin/bash ssbadmin 2>/dev/null || true
echo "ssbadmin:SSBCloud2025!" | chpasswd
usermod -aG sudo ssbadmin
usermod -aG docker ssbadmin
mkdir -p /home/ssbadmin/.ssh
chmod 700 /home/ssbadmin/.ssh
chown -R ssbadmin:ssbadmin /home/ssbadmin/.ssh

# ====== CREATE DIRECTORIES ======
echo "[11/12] Creating application directories..."
mkdir -p /var/www/ssb-cloud-api/logs
mkdir -p /var/www/ssb-cloud-api/uploads
mkdir -p /var/www/ssb-releases/releases
chown -R ssbadmin:ssbadmin /var/www/ssb-cloud-api
chown -R ssbadmin:ssbadmin /var/www/ssb-releases

# ====== POSTGRESQL DATABASE ======
echo "[12/12] Setting up PostgreSQL..."
sudo -u postgres psql << 'SQLEOF'
CREATE DATABASE ssb_cloud;
CREATE USER ssbadmin WITH ENCRYPTED PASSWORD 'SSBCloud2025DB!';
GRANT ALL PRIVILEGES ON DATABASE ssb_cloud TO ssbadmin;
\c ssb_cloud
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    telegram_id VARCHAR(50),
    verified BOOLEAN DEFAULT FALSE,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Licenses table
CREATE TABLE IF NOT EXISTS licenses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    license_key VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id),
    plan VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    hwid VARCHAR(255),
    expires_at TIMESTAMP NOT NULL,
    activated_at TIMESTAMP,
    last_validated TIMESTAMP,
    cloud_session_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id),
    plan VARCHAR(50) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    tx_hash VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    license_id UUID REFERENCES licenses(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Cloud Engines table
CREATE TABLE IF NOT EXISTS cloud_engines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) UNIQUE,
    container_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'stopped',
    last_heartbeat TIMESTAMP,
    tokens_scanned INTEGER DEFAULT 0,
    trades_today INTEGER DEFAULT 0,
    open_positions INTEGER DEFAULT 0,
    pnl_today DECIMAL(10,4) DEFAULT 0,
    started_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User Settings table
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) UNIQUE,
    buy_amount DECIMAL(10,4) DEFAULT 0.1,
    take_profit DECIMAL(5,2) DEFAULT 250,
    stop_loss DECIMAL(5,2) DEFAULT 60,
    min_liq DECIMAL(10,2) DEFAULT 10000,
    min_vol DECIMAL(10,2) DEFAULT 5000,
    filters_on BOOLEAN DEFAULT TRUE,
    slippage DECIMAL(5,2) DEFAULT 15,
    priority_fee DECIMAL(10,6) DEFAULT 0.0005,
    mode VARCHAR(20) DEFAULT 'dry_run',
    telegram_alerts BOOLEAN DEFAULT TRUE,
    max_positions INTEGER DEFAULT 3,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Activity Logs table
CREATE TABLE IF NOT EXISTS activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    details JSONB,
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_licenses_user ON licenses(user_id);
CREATE INDEX IF NOT EXISTS idx_licenses_key ON licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_engines_user ON cloud_engines(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_user ON activity_logs(user_id);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ssbadmin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ssbadmin;
SQLEOF

# ====== INSTALL CERTBOT ======
echo "Installing Certbot..."
apt install -y certbot python3-certbot-nginx

echo ""
echo "========================================"
echo "✅ VPS SETUP COMPLETE!"
echo "========================================"
echo ""
echo "Installed:"
echo "  ✓ Python 3.11"
echo "  ✓ Node.js 18 + PM2"
echo "  ✓ PostgreSQL (database: ssb_cloud)"
echo "  ✓ Nginx"
echo "  ✓ Docker"
echo "  ✓ Fail2Ban"
echo "  ✓ UFW Firewall (22, 80, 443)"
echo "  ✓ Certbot"
echo ""
echo "User created: ssbadmin (password: SSBCloud2025!)"
echo "Database: ssb_cloud (user: ssbadmin)"
echo ""
echo "NEXT STEPS:"
echo "1. Upload application code to /var/www/ssb-cloud-api/"
echo "2. Configure Nginx (run: bash /root/setup-nginx.sh)"
echo "3. Add DNS records at Namecheap"
echo "4. Install SSL certificates"
echo ""
