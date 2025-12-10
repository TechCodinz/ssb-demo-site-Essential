"""
Sol Sniper Bot PRO - SaaS Main Application
Production-ready FastAPI application
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import init_db, async_session_maker
from app.core.security import SecurityHeadersMiddleware, rate_limiter
from app.services.redis_service import redis_service
from app.services.cloud_engine import cloud_engine, start_engine_monitor
from app.api.routes import auth, billing, bot, admin, telegram
from app.api.routes import cloud_auth, cloud_admin, cloud_instance, cloud_signals, cloud_divine, cloud_infra, cloud_license
from app.services.scheduler import start_background_tasks
from app.services.rpc_manager import rpc_manager, start_rpc_manager
from app.services.infrastructure import start_infrastructure, stop_infrastructure
from app.services.usdt_payments import start_payment_service
from app.services.tx_relay import start_tx_relay
from app.services.usage_monitor import start_usage_monitor


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("🚀 Starting Sol Sniper Bot PRO - Cloud SaaS")
    
    # Initialize database
    await init_db()
    print("✅ Database initialized")
    
    # Seed plans if not exist
    await seed_plans()
    print("✅ Plans seeded")
    
    # Create admin token if not exist
    await seed_admin_token()
    print("✅ Admin token seeded")
    
    # Connect to Redis
    await redis_service.connect()
    print("✅ Redis connected")
    
    # Start background scheduler
    start_background_tasks()
    print("✅ Background scheduler started")
    
    # Start cloud engine health monitor
    start_engine_monitor()
    print("✅ Cloud engine monitor started")
    
    # Start RPC manager with health checks
    await start_rpc_manager()
    print("✅ RPC Manager started")
    
    # Start infrastructure services (DexScreener, Pump.fun, etc)
    await start_infrastructure()
    print("✅ Infrastructure services started")
    
    # Start payment monitoring
    await start_payment_service()
    print("✅ Payment service started")
    
    # Start transaction relay
    await start_tx_relay()
    print("✅ Transaction relay started")
    
    # Start usage monitor
    await start_usage_monitor()
    print("✅ Usage monitor started")
    
    yield
    
    # Shutdown
    await stop_infrastructure()
    await redis_service.disconnect()
    print("🛑 Shutdown complete")


async def seed_plans():
    """Seed default plans if they don't exist"""
    from sqlalchemy import select
    from app.models.models import Plan
    
    async with async_session_maker() as db:
        result = await db.execute(select(Plan))
        if result.scalar_one_or_none():
            return  # Plans already exist
        
        plans = [
            Plan(
                id="standard",
                name="STANDARD",
                billing_type="lifetime",
                lifetime_price=199.0,
                engine_profile="STANDARD",
                max_trades_per_hour=7,
                max_open_positions=5,
                min_confidence_score=75.0,
                notes="Beginner Safety Engine - Conservative pace, safer filters"
            ),
            Plan(
                id="pro",
                name="PRO",
                billing_type="lifetime",
                lifetime_price=499.0,
                engine_profile="PRO",
                max_trades_per_hour=12,
                max_open_positions=8,
                min_confidence_score=70.0,
                notes="Balanced Growth Engine - Full LIVE trading with optimized risk/reward"
            ),
            Plan(
                id="elite",
                name="ELITE",
                billing_type="lifetime",
                lifetime_price=899.0,
                engine_profile="ELITE",
                max_trades_per_hour=18,
                max_open_positions=10,
                min_confidence_score=67.0,
                notes="Aggressive Momentum Engine - Fastest entries, maximum profit potential"
            ),
        ]
        
        for plan in plans:
            db.add(plan)
        
        await db.commit()


async def seed_admin_token():
    """Create initial admin master token if not exists"""
    from sqlalchemy import select
    from app.models.models import AdminToken
    import random
    import string
    
    async with async_session_maker() as db:
        result = await db.execute(select(AdminToken))
        if result.scalar_one_or_none():
            return  # Admin token already exists
        
        # Generate master token
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(random.choices(chars, k=16))
        token = f"ADMIN-MASTER-{random_part}"
        
        admin_token = AdminToken(
            token=token,
            name="Master Admin"
        )
        db.add(admin_token)
        await db.commit()
        
        print(f"🔐 Admin Master Token Created: {token}")
        print("   ⚠️  Save this token! It won't be shown again.")


# ============================================================
# APP INITIALIZATION
# ============================================================

app = FastAPI(
    title="Sol Sniper Bot PRO - Cloud SaaS",
    version="2.0.0",
    lifespan=lifespan
)

# Static files and templates
static_path = os.path.join(os.path.dirname(__file__), "static")
templates_path = os.path.join(os.path.dirname(__file__), "templates")

if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

templates = Jinja2Templates(directory=templates_path) if os.path.exists(templates_path) else None

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(bot.router)
app.include_router(admin.router)
app.include_router(telegram.router)

# Cloud SaaS routes
app.include_router(cloud_auth.router)
app.include_router(cloud_admin.router)
app.include_router(cloud_instance.router)
app.include_router(cloud_signals.router)
app.include_router(cloud_divine.router)
app.include_router(cloud_infra.router)
app.include_router(cloud_license.router)


# ============================================================
# DASHBOARD ROUTE
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the marketing landing page"""
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the registration page"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Serve the pricing page"""
    return templates.TemplateResponse("pricing.html", {"request": request})


# ============================================================
# CLOUD SAAS PAGES
# ============================================================

@app.get("/cloud-login", response_class=HTMLResponse)
async def cloud_login_page(request: Request):
    """Cloud token login page"""
    return templates.TemplateResponse("cloud_login.html", {"request": request})


@app.get("/cloud-dashboard", response_class=HTMLResponse)
async def cloud_dashboard_page(request: Request):
    """Cloud user dashboard"""
    return templates.TemplateResponse("cloud_dashboard.html", {"request": request})


@app.get("/cloud-renew", response_class=HTMLResponse)
async def cloud_renew_page(request: Request):
    """Cloud subscription renewal page"""
    return templates.TemplateResponse("cloud_renew.html", {"request": request})


@app.get("/cloud-admin", response_class=HTMLResponse)
async def cloud_admin_page(request: Request):
    """Cloud admin panel"""
    return templates.TemplateResponse("cloud_admin.html", {"request": request})


@app.get("/cloud-error", response_class=HTMLResponse)
async def cloud_error_page(request: Request):
    """Cloud error pages (expired, suspended, invalid, locked)"""
    return templates.TemplateResponse("cloud_error.html", {"request": request})


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0"}


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Sol Sniper Bot PRO - Cloud SaaS")
    print("  Open http://localhost:8000 in your browser")
    print("="*60 + "\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
