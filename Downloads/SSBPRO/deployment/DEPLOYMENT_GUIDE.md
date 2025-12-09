# SSB PRO Cloud - VPS Deployment Guide

## 🖥️ VPS Details
- **IP:** `194.163.151.208`
- **OS:** Ubuntu (Contabo Cloud VPS 20)
- **RAM:** 12 GB
- **CPU:** 6 cores

---

## 📋 Step-by-Step Deployment

### 1️⃣ Connect to VPS

First, SSH into your VPS. Check your Contabo email for the root password.

```bash
ssh root@194.163.151.208
```

---

### 2️⃣ Upload Deployment Scripts

On your **local machine**, upload the scripts:

```bash
cd C:\Users\User\Downloads\SSBPRO\deployment
scp ssb-setup-part1.sh ssb-setup-part2.sh ssb-setup-part3.sh deploy-app.sh root@194.163.151.208:/root/
```

---

### 3️⃣ Run Setup Scripts (On VPS)

```bash
# Make executable
chmod +x /root/ssb-setup-*.sh /root/deploy-app.sh

# Part 1: Install base packages (Python, Node, Nginx, Docker, etc.)
bash /root/ssb-setup-part1.sh

# Part 2: Setup PostgreSQL database + tables
bash /root/ssb-setup-part2.sh

# Part 3: Configure Nginx reverse proxy
bash /root/ssb-setup-part3.sh
```

---

### 4️⃣ Upload Application Code

On your **local machine**:

```bash
cd C:\Users\User\Downloads\SSBPRO
scp -r saas_platform/* root@194.163.151.208:/var/www/ssb-cloud-api/
```

---

### 5️⃣ Deploy Application

On VPS:

```bash
bash /root/deploy-app.sh
```

---

### 6️⃣ Configure DNS (Namecheap/Domain Registrar)

Add these DNS records:

| Type | Host | Value |
|------|------|-------|
| A | @ | 194.163.151.208 |
| A | api | 194.163.151.208 |
| A | license | 194.163.151.208 |
| A | engine | 194.163.151.208 |
| A | download | 194.163.151.208 |
| A | admin | 194.163.151.208 |
| A | orders | 194.163.151.208 |
| CNAME | www | ssbpro.dev |

---

### 7️⃣ Install SSL Certificates

After DNS propagates (5-30 minutes):

```bash
certbot --nginx -d ssbpro.dev -d www.ssbpro.dev -d api.ssbpro.dev -d license.ssbpro.dev -d engine.ssbpro.dev -d download.ssbpro.dev -d admin.ssbpro.dev -d orders.ssbpro.dev
```

---

### 8️⃣ Verify Deployment

Check services:
```bash
pm2 list
pm2 logs ssb-api
```

Test API:
```bash
curl http://localhost:8000/health
```

---

## 🔧 Important Files to Edit

1. **`.env`** in `/var/www/ssb-cloud-api/`:
   - Set `JWT_SECRET` to something secure
   - Add `TELEGRAM_BOT_TOKEN`
   - Configure `SMTP_*` for emails

2. **Database password** if you changed it

---

## ✅ Deployment Checklist

- [ ] VPS connected via SSH
- [ ] Scripts uploaded and executed
- [ ] PostgreSQL running with tables
- [ ] Nginx configured with all subdomains
- [ ] Application code uploaded
- [ ] PM2 processes running
- [ ] DNS records added
- [ ] SSL certificates installed
- [ ] .env configured with secrets
- [ ] API responding on https://api.ssbpro.dev
