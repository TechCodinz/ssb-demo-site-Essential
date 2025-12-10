"""
Sol Sniper Bot PRO - SaaS Configuration
Production-ready settings with security and cloud features.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Sol Sniper Bot PRO - Cloud"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_SUPER_SECRET_KEY_2025")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # development, staging, production
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://ssb:ssb_password@localhost:5432/ssb_saas")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "CHANGE_ME_JWT_SECRET_2025")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # USDT TRC20 Payments
    USDT_WALLET_ADDRESS: str = os.getenv("USDT_WALLET_ADDRESS", "TBxck6t1a3pZE2YLho4Su1PcGKd2yK2zD4")
    TRON_API_KEY: str = os.getenv("TRON_API_KEY", "")
    
    # Desktop Plans Pricing (USD - Lifetime)
    PRICE_STANDARD_LIFETIME: float = 199.0
    PRICE_PRO_LIFETIME: float = 499.0
    PRICE_ELITE_LIFETIME: float = 899.0
    
    # Cloud Plans Pricing (USD - Monthly) - CLOUD SNIPER
    CLOUD_PRICE_STANDARD: float = 79.0   # CLOUD SNIPER
    CLOUD_PRICE_PRO: float = 149.0       # CLOUD SNIPER PRO
    CLOUD_PRICE_ELITE: float = 249.0     # CLOUD SNIPER ELITE
    
    # Cloud Engine Settings
    CLOUD_INSTANCE_ID: str = os.getenv("CLOUD_INSTANCE_ID", "SSB-CLOUD-MAIN-01")
    CLOUD_HEARTBEAT_INTERVAL: int = 30  # seconds
    CLOUD_HEARTBEAT_TIMEOUT: int = 90  # seconds before marking inactive
    CLOUD_MAX_RESTART_ATTEMPTS: int = 3
    
    # Plan Limits
    PLAN_LIMITS: dict = {
        "STANDARD": {
            "max_trades_per_hour": 7,
            "max_positions": 5,
            "min_confidence": 75.0,
            "uptime_hours": 18,  # Max hours per day
            "queue_priority": 3,  # Lower = slower
            "devices_allowed": 1,
            "live_trading": True
        },
        "PRO": {
            "max_trades_per_hour": 12,
            "max_positions": 8,
            "min_confidence": 70.0,
            "uptime_hours": 24,
            "queue_priority": 2,
            "devices_allowed": 1,
            "live_trading": True
        },
        "ELITE": {
            "max_trades_per_hour": 18,
            "max_positions": 10,
            "min_confidence": 67.0,
            "uptime_hours": 24,
            "queue_priority": 1,  # Highest priority
            "devices_allowed": 3,
            "live_trading": True
        },
        # ============================================================
        # DEMO MODE - FULL POWER DRY RUN FOR MARKETING
        # ============================================================
        # Users see EVERYTHING the bot can do:
        # - Real token detection
        # - Real AI analysis
        # - Real signals (LEGENDARY, ULTRA, STRONG)
        # - Real whale alerts
        # - Real cascade detection  
        # - Simulated trades with full P&L tracking
        # ONLY restriction: No real transactions
        # This is the CONVERSION FUNNEL - show power, drive upgrades!
        "DEMO": {
            "max_trades_per_hour": 50,  # HIGH - show lots of opportunities
            "max_positions": 10,  # Show full portfolio capability
            "min_confidence": 65.0,  # LOW - show more signals
            "uptime_hours": 24,  # Full 24/7 access
            "queue_priority": 2,  # Good priority (not last)
            "devices_allowed": 1,
            "live_trading": False,  # DRY RUN only - NO real trades
            # DEMO-SPECIFIC FEATURES
            "full_algorithm": True,  # Show Ultra Algorithm in action
            "show_signals": True,  # Show all signal types
            "show_whale_alerts": True,  # Show whale tracking
            "show_cascades": True,  # Show momentum cascades
            "show_protection": True,  # Show divine protection
            "simulated_pnl": True,  # Track simulated profits
            "demo_mode_banner": True  # Show "UPGRADE TO TRADE LIVE"
        }
    }
    
    # Rate Limiting
    RATE_LIMIT_LOGIN: int = 5  # attempts per minute
    RATE_LIMIT_API: int = 100  # requests per minute
    RATE_LIMIT_VERIFY: int = 3  # code attempts per 5 mins
    MAX_FAILED_LOGINS: int = 5  # before account lock
    
    # Security
    MAX_IP_CHANGES_PER_DAY: int = 2
    SESSION_TIMEOUT_HOURS: int = 24
    
    # Email Settings
    EMAIL_DEV_MODE: bool = os.getenv("EMAIL_DEV_MODE", "true").lower() == "true"
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "noreply@ssbpro.cloud")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "SSB Cloud")
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_CHAT_ID: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
    
    # Bot Defaults
    DEFAULT_RPC_URL: str = "https://api.mainnet-beta.solana.com"
    
    # RPC Providers (FREE TIER)
    HELIUS_RPC: str = os.getenv("HELIUS_RPC", "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY")
    ANKR_RPC: str = os.getenv("ANKR_RPC", "https://rpc.ankr.com/solana")
    QUICKNODE_RPC: str = os.getenv("QUICKNODE_RPC", "https://api.mainnet-beta.solana.com")
    
    # RPC Providers (PREMIUM - for later upgrade)
    HELIUS_RPC_PREMIUM: str = os.getenv("HELIUS_RPC_PREMIUM", "")
    TRITON_RPC: str = os.getenv("TRITON_RPC", "")
    QUICKNODE_RPC_PREMIUM: str = os.getenv("QUICKNODE_RPC_PREMIUM", "")
    
    # RPC Configuration
    RPC_TIER: str = os.getenv("RPC_TIER", "FREE")  # FREE or PREMIUM
    RPC_FAIL_THRESHOLD: int = 3
    RPC_WEIGHT_HELIUS: float = 0.6
    RPC_WEIGHT_ANKR: float = 0.3
    RPC_WEIGHT_QUICKNODE: float = 0.1
    RPC_HEALTH_CHECK_INTERVAL: int = 30
    
    # Infrastructure Settings
    DEXSCREENER_CACHE_TTL: int = 60
    HONEYPOT_CACHE_TTL: int = 300
    JUPITER_SLIPPAGE_BPS: int = 100
    PUMP_STREAM_RECONNECT_DELAY: int = 5
    
    # Encryption key for private keys
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "CHANGE_ME_32_BYTE_KEY_FOR_AES256")
    
    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8000")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


# Export for use in AsyncSessionLocal alias
AsyncSessionLocal = None  # Populated by database.py

