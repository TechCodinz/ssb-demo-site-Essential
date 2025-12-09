#!/bin/bash
# ============================================
# SSB PRO Cloud - VPS Setup Script (Part 1)
# Server: 194.163.151.208
# Run as root
# ============================================

set -e

echo "🚀 SSB PRO Cloud - VPS Setup Starting..."

# ====== STEP 1: UPDATE SYSTEM ======
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# ====== STEP 2: INSTALL BASE PACKAGES ======
echo "📦 Installing base packages..."
apt install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    build-essential

# ====== STEP 3: INSTALL PYTHON 3.11 ======
echo "🐍 Installing Python 3.11..."
add-apt-repository ppa:deadsnakes/ppa -y
apt update
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Verify
python3 --version

# ====== STEP 4: INSTALL NODE.JS 18 ======
echo "📗 Installing Node.js 18..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Install PM2 globally
npm install -g pm2

# Verify
node --version
npm --version
pm2 --version

# ====== STEP 5: INSTALL POSTGRESQL ======
echo "🐘 Installing PostgreSQL..."
apt install -y postgresql postgresql-contrib

# Start and enable
systemctl start postgresql
systemctl enable postgresql

# ====== STEP 6: INSTALL NGINX ======
echo "🌐 Installing Nginx..."
apt install -y nginx

systemctl start nginx
systemctl enable nginx

# ====== STEP 7: INSTALL DOCKER ======
echo "🐳 Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Add docker to current user
usermod -aG docker $USER

systemctl start docker
systemctl enable docker

# ====== STEP 8: INSTALL FAIL2BAN ======
echo "🛡️ Installing Fail2Ban..."
apt install -y fail2ban

# Configure fail2ban
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

# ====== STEP 9: CONFIGURE UFW FIREWALL ======
echo "🔥 Configuring UFW Firewall..."
apt install -y ufw

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 5173/tcp  # Dev (optional)

# Enable firewall
echo "y" | ufw enable

ufw status verbose

# ====== STEP 10: CREATE SSBADMIN USER ======
echo "👤 Creating ssbadmin user..."
useradd -m -s /bin/bash ssbadmin
usermod -aG sudo ssbadmin
usermod -aG docker ssbadmin

# Set password (change this!)
echo "ssbadmin:SSBCloud2025!" | chpasswd

# Create .ssh directory for ssbadmin
mkdir -p /home/ssbadmin/.ssh
chmod 700 /home/ssbadmin/.ssh
chown -R ssbadmin:ssbadmin /home/ssbadmin/.ssh

echo "✅ Part 1 Complete!"
echo ""
echo "Next steps:"
echo "1. Run: bash /root/ssb-setup-part2.sh"
echo "2. Configure SSH keys"
echo "3. Setup database"
