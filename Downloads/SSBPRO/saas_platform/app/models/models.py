"""
Sol Sniper Bot PRO - Database Models
Complete schema for SaaS platform
"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, 
    ForeignKey, Text, Enum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


# ============================================================
# ENUMS
# ============================================================

class BillingType(str, enum.Enum):
    MONTHLY = "monthly"
    LIFETIME = "lifetime"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BotStatus(str, enum.Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class BotMode(str, enum.Enum):
    DRY_RUN = "DRY_RUN"
    LIVE = "LIVE"


class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


# ============================================================
# USERS
# ============================================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    stripe_customer_id = Column(String(255), nullable=True)
    telegram_username = Column(String(100), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="user", lazy="selectin")
    bot_instance = relationship("BotInstance", back_populates="user", uselist=False, lazy="selectin")


# ============================================================
# PLANS
# ============================================================

class Plan(Base):
    __tablename__ = "plans"
    
    id = Column(String(50), primary_key=True)  # standard, pro, elite
    name = Column(String(100), nullable=False)
    billing_type = Column(String(20), default="lifetime")
    monthly_price = Column(Float, nullable=True)
    lifetime_price = Column(Float, nullable=False)
    engine_profile = Column(String(50), nullable=False)  # STANDARD, PRO, ELITE
    max_trades_per_hour = Column(Integer, default=12)
    max_open_positions = Column(Integer, default=8)
    min_confidence_score = Column(Float, default=70.0)
    notes = Column(Text, nullable=True)
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")


# ============================================================
# SUBSCRIPTIONS
# ============================================================

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_id = Column(String(50), ForeignKey("plans.id"), nullable=False)
    billing_type = Column(Enum(BillingType), default=BillingType.LIFETIME)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    stripe_subscription_id = Column(String(255), nullable=True)
    crypto_tx = Column(String(100), nullable=True)
    current_period_start = Column(DateTime, default=datetime.utcnow)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")


# ============================================================
# BOT INSTANCES
# ============================================================

class BotInstance(Base):
    __tablename__ = "bot_instances"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    status = Column(Enum(BotStatus), default=BotStatus.STOPPED)
    mode = Column(Enum(BotMode), default=BotMode.DRY_RUN)
    engine_profile = Column(String(50), default="PRO")
    
    # Trading Config
    rpc_url = Column(String(500), nullable=True)
    buy_amount_sol = Column(Float, default=0.25)
    min_liquidity_usd = Column(Float, default=8000)
    min_volume_5m = Column(Float, default=15000)
    take_profit_percent = Column(Float, default=250)
    stop_loss_percent = Column(Float, default=60)
    max_trades_per_hour = Column(Integer, default=12)
    max_open_positions = Column(Integer, default=8)
    min_confidence_score = Column(Float, default=70)
    session_start_hour_utc = Column(Integer, default=0)
    session_end_hour_utc = Column(Integer, default=23)
    
    # Wallet (encrypted)
    private_key_encrypted = Column(Text, nullable=True)
    
    # Telegram
    telegram_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="bot_instance")
    logs = relationship("BotLog", back_populates="bot_instance", lazy="dynamic")


# ============================================================
# BOT LOGS
# ============================================================

class BotLog(Base):
    __tablename__ = "bot_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_instance_id = Column(UUID(as_uuid=True), ForeignKey("bot_instances.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(Enum(LogLevel), default=LogLevel.INFO)
    message = Column(Text, nullable=False)
    extra_json = Column(JSON, nullable=True)
    
    # Relationships
    bot_instance = relationship("BotInstance", back_populates="logs")


# ============================================================
# CRYPTO ORDERS
# ============================================================

class CryptoOrder(Base):
    __tablename__ = "crypto_orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_id = Column(String(50), ForeignKey("plans.id"), nullable=False)
    amount_usdt = Column(Float, nullable=False)
    reference_code = Column(String(50), unique=True, nullable=False)
    tx_hash = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")  # pending, verified, expired
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)


# ============================================================
# CLOUD USERS (TOKEN-BASED AUTH)
# ============================================================

class CloudUser(Base):
    """
    Cloud SaaS user with token-only authentication.
    Token format: CLOUD-{PLAN}-{12_RANDOM_CHARS}
    """
    __tablename__ = "cloud_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic Info
    email = Column(String(255), unique=True, nullable=False, index=True)
    wallet = Column(String(100), nullable=True)
    telegram = Column(String(100), nullable=True)
    
    # Plan & Token
    plan = Column(String(20), nullable=False)  # STANDARD, PRO, ELITE
    token = Column(String(50), unique=True, nullable=False, index=True)  # CLOUD-ELITE-XXXX
    
    # Subscription
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Email Verification
    email_verified = Column(Boolean, default=False)
    email_verification_code = Column(String(100), nullable=True)  # Hashed
    email_code_expires_at = Column(DateTime, nullable=True)
    
    # Device Binding (Anti-Share)
    bound_device_id = Column(String(255), nullable=True)
    bound_cloud_instance = Column(String(255), nullable=True)
    bound_ip = Column(String(50), nullable=True)
    bound_browser_fingerprint = Column(String(255), nullable=True)
    binding_locked = Column(Boolean, default=False)  # True after first login
    
    # IP/Device Limits
    ip_changes_today = Column(Integer, default=0)
    last_ip_change_date = Column(DateTime, nullable=True)
    device_reset_at = Column(DateTime, nullable=True)  # Last device reset
    
    # Login Tracking
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(50), nullable=True)
    login_ips = Column(JSON, default=[])  # Track last 20 IPs
    login_attempts_today = Column(Integer, default=0)  # Block after 5 failed
    last_failed_login_at = Column(DateTime, nullable=True)
    
    # Heartbeat
    last_heartbeat_at = Column(DateTime, nullable=True)
    
    # Security Flags
    is_suspicious = Column(Boolean, default=False)
    suspension_reason = Column(String(255), nullable=True)
    is_locked = Column(Boolean, default=False)  # True after 5 failed attempts
    
    # Trading Mode (for expired users)
    trading_mode = Column(String(20), default="LIVE")  # LIVE, DRY_RUN, FROZEN
    
    # Relationships
    heartbeats = relationship("CloudHeartbeat", back_populates="cloud_user", lazy="dynamic")
    activity_logs = relationship("CloudActivityLog", back_populates="cloud_user", lazy="dynamic")


class CloudHeartbeat(Base):
    """
    Heartbeat tracking for license guardian.
    Sent every 20 seconds, stores last 20 per user.
    """
    __tablename__ = "cloud_heartbeats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cloud_user_id = Column(UUID(as_uuid=True), ForeignKey("cloud_users.id"), nullable=False, index=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String(50), nullable=True)
    device_id = Column(String(255), nullable=True)
    browser_fingerprint = Column(String(255), nullable=True)
    cloud_instance_id = Column(String(255), nullable=True)
    
    # Relationships
    cloud_user = relationship("CloudUser", back_populates="heartbeats")


class CloudActivityLog(Base):
    """
    Activity logging for admin surveillance.
    Tracks logins, activations, renewals, suspensions.
    """
    __tablename__ = "cloud_activity_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cloud_user_id = Column(UUID(as_uuid=True), ForeignKey("cloud_users.id"), nullable=True, index=True)
    
    action = Column(String(50), nullable=False)  # login, activation, renewal, suspension, device_change, ip_change, abuse_detected
    ip_address = Column(String(50), nullable=True)
    device_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    details = Column(JSON, nullable=True)
    
    # Relationships
    cloud_user = relationship("CloudUser", back_populates="activity_logs")


class EmailVerification(Base):
    """
    Email verification codes for login and device changes.
    Codes expire after 5 minutes.
    """
    __tablename__ = "email_verifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cloud_user_id = Column(UUID(as_uuid=True), ForeignKey("cloud_users.id"), nullable=False, index=True)
    
    email = Column(String(255), nullable=False)
    code_hash = Column(String(255), nullable=False)  # SHA256 of 6-digit code
    purpose = Column(String(50), nullable=False)  # first_login, device_change, ip_verification
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)  # Rate limit: max 3 attempts


class AdminToken(Base):
    """
    Admin master token for full root access.
    Format: ADMIN-MASTER-{RANDOM}
    """
    __tablename__ = "admin_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)  # Admin name
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Permissions (all default True for master token)
    can_suspend_users = Column(Boolean, default=True)
    can_renew_users = Column(Boolean, default=True)
    can_override_tokens = Column(Boolean, default=True)
    can_view_logs = Column(Boolean, default=True)
    can_kill_switch = Column(Boolean, default=True)
    can_reset_bindings = Column(Boolean, default=True)
    can_monitor_realtime = Column(Boolean, default=True)

