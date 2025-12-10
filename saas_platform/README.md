# Sol Sniper Bot PRO - Cloud SaaS Platform

Production-ready SaaS platform for the Sol Sniper Bot with USDT crypto payments.

## 🚀 Quick Start (Development)

```bash
# 1. Start PostgreSQL and Redis (using Docker)
docker-compose up -d postgres redis

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Run the API server
cd app
python main.py

# 6. In another terminal, run the worker
python worker/engine.py
```

Open http://localhost:8000 in your browser.

## 🐳 Production Deployment (Docker)

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f api
docker-compose logs -f worker
```

## 📁 Project Structure

```
saas_platform/
├── app/
│   ├── api/routes/          # API endpoints
│   │   ├── auth.py          # Authentication
│   │   ├── billing.py       # USDT payments
│   │   ├── bot.py           # Bot control
│   │   └── admin.py         # Admin panel
│   ├── core/
│   │   ├── config.py        # Settings
│   │   ├── database.py      # PostgreSQL
│   │   └── security.py      # JWT/encryption
│   ├── models/
│   │   └── models.py        # SQLAlchemy models
│   ├── services/
│   │   ├── bot_manager.py   # Bot lifecycle
│   │   └── redis_service.py # Pub/sub
│   ├── worker/
│   │   └── engine.py        # Trading engine
│   └── main.py              # FastAPI app
├── templates/               # HTML pages
├── docker-compose.yml       # Deployment
├── Dockerfile.api           # API container
├── Dockerfile.worker        # Worker container
└── requirements.txt         # Dependencies
```

## 🔑 API Endpoints

### Authentication
- `POST /auth/register` - Create account
- `POST /auth/login` - Login
- `GET /auth/me` - Current user
- `POST /auth/logout` - Logout

### Billing
- `GET /billing/plans` - List plans
- `POST /billing/create-crypto-order` - Create payment order
- `POST /billing/verify-crypto-tx` - Verify USDT payment
- `GET /billing/subscription` - Get subscription

### Bot
- `GET /bot/status` - Bot status & config
- `POST /bot/start` - Start bot
- `POST /bot/stop` - Stop bot
- `POST /bot/config` - Update config
- `GET /bot/logs` - Get logs
- `WS /bot/ws/logs` - Live log stream

### Admin
- `GET /admin/users` - List users
- `POST /admin/override-plan` - Override plan
- `POST /admin/activate-lifetime` - Activate lifetime
- `GET /admin/stats` - System stats

## 💰 Plans

| Plan | Price | Engine | Trades/hr | Positions |
|------|-------|--------|-----------|-----------|
| STANDARD | $199 | Conservative | 7 | 5 |
| PRO | $499 | Balanced | 12 | 8 |
| ELITE | $899 | Aggressive | 18 | 10 |

## 🔒 Security

- JWT tokens in HTTP-only cookies
- Private keys encrypted with AES-256
- USDT payments verified via TronScan
- Admin-only endpoints protected

## 📝 Environment Variables

```
SECRET_KEY=your_secret_key
JWT_SECRET=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
USDT_WALLET_ADDRESS=your_tron_address
```

## ✅ Production Checklist

- [ ] Update `.env` with production secrets
- [ ] Set `DEBUG=false`
- [ ] Configure SSL/HTTPS
- [ ] Set up domain and DNS
- [ ] Enable Nginx reverse proxy
- [ ] Set up database backups
- [ ] Configure logging/monitoring
