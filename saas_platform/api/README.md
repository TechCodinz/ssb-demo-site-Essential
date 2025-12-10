# SSB PRO SaaS Platform - API Server

## Quick Start
```bash
cd saas_platform
pip install -r requirements.txt
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints
- Auth: `/v1/login`, `/v1/signup`, `/v1/email-verify`
- License: `/v1/license/validate`, `/v1/license/activate`
- Orders: `/v1/orders/create`, `/v1/orders/webhook`
- Bot: `/v1/bot/health`, `/v1/bot/update-check`

## Environment Variables
Copy `.env.example` to `.env` and configure:
- DATABASE_URL
- JWT_SECRET
- SMTP settings
