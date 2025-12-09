#!/bin/bash
# Sol Sniper Bot PRO - VPS Deployment Script
# Run this on a fresh Ubuntu 22.04 VPS

set -e

echo "================================================"
echo "  Sol Sniper Bot PRO - Deployment Script"
echo "================================================"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Variables
DOMAIN=${1:-"yourdomain.com"}
EMAIL=${2:-"admin@yourdomain.com"}
APP_DIR="/opt/ssb-saas"

echo -e "${CYAN}[1/7] Updating system...${NC}"
apt update && apt upgrade -y

echo -e "${CYAN}[2/7] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

echo -e "${CYAN}[3/7] Installing Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    apt install -y docker-compose
fi

echo -e "${CYAN}[4/7] Installing Nginx and Certbot...${NC}"
apt install -y nginx certbot python3-certbot-nginx

echo -e "${CYAN}[5/7] Creating application directory...${NC}"
mkdir -p $APP_DIR
cd $APP_DIR

# Check if files exist, if not prompt for git clone
if [ ! -f "docker-compose.yml" ]; then
    echo "Please copy your saas_platform folder to $APP_DIR"
    echo "Or git clone your repository here"
    exit 1
fi

echo -e "${CYAN}[6/7] Setting up environment...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    
    # Generate random secrets
    SECRET_KEY=$(openssl rand -hex 32)
    JWT_SECRET=$(openssl rand -hex 32)
    ENCRYPT_KEY=$(openssl rand -hex 16)
    
    # Update .env with generated secrets
    sed -i "s/your_super_secret_key_here_2025/$SECRET_KEY/" .env
    sed -i "s/your_jwt_secret_key_here_2025/$JWT_SECRET/" .env
    sed -i "s/your_32_byte_encryption_key/$ENCRYPT_KEY/" .env
    
    echo -e "${GREEN}Generated secure random secrets in .env${NC}"
    echo "IMPORTANT: Edit .env and set your USDT_WALLET_ADDRESS"
fi

echo -e "${CYAN}[7/7] Starting services...${NC}"
docker-compose up -d --build

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Your app is running at: http://$(curl -s ifconfig.me):8000"
echo ""
echo "Next steps:"
echo "1. Edit /opt/ssb-saas/.env with your USDT wallet address"
echo "2. Run: sudo ./setup-ssl.sh $DOMAIN $EMAIL"
echo "3. Point your domain to this server's IP"
echo ""
