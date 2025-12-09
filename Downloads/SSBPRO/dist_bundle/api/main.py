"""
SSB PRO SaaS Platform - Main API Entry Point
FastAPI application with JWT auth, license management, and order processing
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

# Import routers
from api.routers import auth, license, orders, user, bot
from api.middleware.rate_limit import RateLimitMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SSB PRO Cloud API",
    description="Sol Sniper Bot PRO - Cloud Trading Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ssbpro.dev",
        "https://app.ssbpro.dev",
        "https://admin.ssbpro.dev",
        "http://localhost:3000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# Include routers
app.include_router(auth.router, prefix="/v1", tags=["Authentication"])
app.include_router(license.router, prefix="/v1/license", tags=["License"])
app.include_router(orders.router, prefix="/v1/orders", tags=["Orders"])
app.include_router(user.router, prefix="/v1/user", tags=["User"])
app.include_router(bot.router, prefix="/v1/bot", tags=["Bot"])


@app.get("/")
async def root():
    return {
        "name": "SSB PRO Cloud API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api.ssbpro.dev"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
