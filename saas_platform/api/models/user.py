from sqlalchemy import Column, String, Boolean, DateTime, Float, Text
from api.database import Base
from datetime import datetime
import secrets

def generate_referral_code():
    return secrets.token_urlsafe(6).upper()[:8]

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: secrets.token_hex(8))
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    plan = Column(String, default="cloud_sniper")
    verified = Column(Boolean, default=False)
    telegram_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Referral System
    referral_code = Column(String, unique=True, index=True, default=generate_referral_code)
    referred_by = Column(String, nullable=True)  # referral_code of referrer
    total_referral_earnings = Column(Float, default=0.0)
    referral_clicks = Column(Float, default=0)  # Track link clicks
    
    # Gamification
    achievement_badges = Column(Text, default="[]")  # JSON array of badge IDs
    total_pnl = Column(Float, default=0.0)  # Lifetime PnL for leaderboard
    win_streak = Column(Float, default=0)  # Current win streak


class ReferralEarning(Base):
    """Tracks individual referral commission events"""
    __tablename__ = "referral_earnings"
    
    id = Column(String, primary_key=True, default=lambda: secrets.token_hex(8))
    user_id = Column(String, index=True)  # The referrer who earns
    referred_user_id = Column(String)  # The user who signed up
    source_order_id = Column(String)  # The order that triggered commission
    amount = Column(Float)  # Commission amount in USD
    status = Column(String, default="pending")  # pending, paid, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

