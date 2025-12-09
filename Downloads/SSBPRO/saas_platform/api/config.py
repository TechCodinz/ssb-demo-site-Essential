"""
SSB PRO - API Configuration
Environment variables and settings
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional, ClassVar


# Plan Pricing
PLAN_PRICES = {
    "cloud_sniper": 79,
    "cloud_sniper_pro": 149,
    "cloud_sniper_elite": 249,
    "standard_local": 199,
    "pro_local": 499,
    "elite_local": 899
}


class Settings(BaseSettings):
    # App
    APP_NAME: str = "SSB PRO Cloud API"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///./ssb_pro.db"
    
    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "ssb-pro-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # SMTP Email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "noreply@ssbpro.dev")
    
    # License
    LICENSE_VALIDATION_INTERVAL_MINUTES: int = 5
    MAX_DEVICES_PER_LICENSE: int = 2
    
    # USDT Payment
    USDT_WALLET: str = "TBxck6t1a3pZE2YLho4Su1PcGKd2yK2zD4"
    USDT_NETWORK: str = "TRC20"
    
    # Admin
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "SSB2025Admin")
    
    class Config:
        env_file = ".env"


settings = Settings()
