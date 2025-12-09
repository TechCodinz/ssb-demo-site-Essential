#!/bin/bash
# ============================================
# SSB PRO Cloud - VPS Setup Script (Part 2)
# Database, Application, and SSL Setup
# ============================================

set -e

echo "🚀 SSB PRO Cloud - Part 2: Application Setup..."

# ====== STEP 1: CREATE APPLICATION DIRECTORIES ======
echo "📁 Creating application directories..."
mkdir -p /var/www/ssb-cloud-api
mkdir -p /var/www/ssb-cloud-api/logs
mkdir -p /var/www/ssb-cloud-api/uploads
mkdir -p /var/www/ssb-releases

chown -R ssbadmin:ssbadmin /var/www/ssb-cloud-api
chown -R ssbadmin:ssbadmin /var/www/ssb-releases

# ====== STEP 2: SETUP POSTGRESQL DATABASE ======
echo "🐘 Setting up PostgreSQL database..."

sudo -u postgres psql << 'EOF'
-- Create database
CREATE DATABASE ssb_cloud;

-- Create user
CREATE USER ssbadmin WITH ENCRYPTED PASSWORD 'SSBCloud2025DB!';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE ssb_cloud TO ssbadmin;

-- Connect to database
\c ssb_cloud

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

EOF

echo "✅ Database created: ssb_cloud"

# ====== STEP 3: CREATE DATABASE TABLES ======
echo "📊 Creating database tables..."

sudo -u postgres psql -d ssb_cloud << 'EOF'

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
CREATE INDEX idx_licenses_user ON licenses(user_id);
CREATE INDEX idx_licenses_key ON licenses(license_key);
CREATE INDEX idx_payments_user ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_engines_user ON cloud_engines(user_id);
CREATE INDEX idx_logs_user ON activity_logs(user_id);
CREATE INDEX idx_logs_action ON activity_logs(action);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ssbadmin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ssbadmin;

EOF

echo "✅ Database tables created!"

# ====== STEP 4: INSTALL CERTBOT FOR SSL ======
echo "🔒 Installing Certbot for SSL..."
apt install -y certbot python3-certbot-nginx

echo "✅ Part 2 Complete!"
echo ""
echo "Database: ssb_cloud"
echo "User: ssbadmin"
echo ""
echo "Next: Run part 3 to configure Nginx and deploy the app"
