"""
Sol Sniper Bot PRO - Cloud Auth Routes
Token-only authentication with email verification, device binding, and heartbeat.
"""
import os
import random
import string
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.config import settings
from app.models.models import (
    CloudUser, CloudHeartbeat, CloudActivityLog, 
    EmailVerification, AdminToken
)

router = APIRouter(prefix="/cloud", tags=["Cloud Auth"])
security = HTTPBearer(auto_error=False)

# Cloud instance identifier (unique per deployment)
CLOUD_INSTANCE_ID = os.getenv("CLOUD_INSTANCE_ID", "SSB-CLOUD-MAIN-01")


# ============================================================
# SCHEMAS
# ============================================================

class TokenLoginRequest(BaseModel):
    token: str

class TokenLoginResponse(BaseModel):
    requires_email_verification: bool
    requires_device_verification: bool
    email_hint: Optional[str] = None
    message: str

class EmailInputRequest(BaseModel):
    token: str
    email: EmailStr

class VerifyCodeRequest(BaseModel):
    token: str
    email: str
    code: str

class AuthSuccessResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    plan: str
    days_remaining: int
    dashboard_url: str

class HeartbeatRequest(BaseModel):
    device_id: str
    browser_fingerprint: Optional[str] = None

class CloudUserResponse(BaseModel):
    email: str
    plan: str
    expires_at: str
    days_remaining: int
    is_active: bool
    last_login_at: Optional[str]


# ============================================================
# HELPERS
# ============================================================

def generate_cloud_token(plan: str) -> str:
    """Generate CLOUD-{PLAN}-{12_RANDOM_CHARS}"""
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=12))
    return f"CLOUD-{plan.upper()}-{random_part}"


def generate_admin_token(name: str) -> str:
    """Generate ADMIN-MASTER-{16_RANDOM_CHARS}"""
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=16))
    return f"ADMIN-MASTER-{random_part}"


def generate_verification_code() -> str:
    """Generate 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


def hash_code(code: str) -> str:
    """Hash verification code with SHA256"""
    return hashlib.sha256(code.encode()).hexdigest()


def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host or "unknown"


async def log_activity(
    db: AsyncSession, 
    user_id: Optional[UUID], 
    action: str, 
    ip: str = None, 
    device_id: str = None, 
    details: dict = None
):
    """Log activity for admin surveillance"""
    log = CloudActivityLog(
        cloud_user_id=user_id,
        action=action,
        ip_address=ip,
        device_id=device_id,
        details=details
    )
    db.add(log)
    await db.flush()


# ============================================================
# TOKEN VALIDATION DEPENDENCY
# ============================================================

async def get_current_cloud_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> CloudUser:
    """Validate cloud token and return user"""
    token = None
    
    if credentials:
        token = credentials.credentials
    
    if not token:
        raise HTTPException(status_code=401, detail="Cloud access token required")
    
    # Find user by token
    result = await db.execute(
        select(CloudUser).where(CloudUser.token == token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid cloud token")
    
    # Check if active
    if not user.is_active:
        raise HTTPException(
            status_code=403, 
            detail=f"Account suspended: {user.suspension_reason or 'Contact admin'}"
        )
    
    # Check expiration
    if user.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=403,
            detail="Subscription expired. Pay USDT to renew."
        )
    
    # Check cloud instance binding
    if user.binding_locked and user.bound_cloud_instance:
        if user.bound_cloud_instance != CLOUD_INSTANCE_ID:
            raise HTTPException(
                status_code=403,
                detail="Access denied. Token bound to different cloud instance."
            )
    
    # Check email verification
    if not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Complete verification to access."
        )
    
    return user


# ============================================================
# LOGIN FLOW
# ============================================================

@router.post("/login", response_model=TokenLoginResponse)
async def cloud_login(
    data: TokenLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 1: Validate token and determine if verification needed.
    Returns whether email or device verification is required.
    """
    client_ip = get_client_ip(request)
    
    # Find user by token
    result = await db.execute(
        select(CloudUser).where(CloudUser.token == data.token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await log_activity(db, None, "login_failed_invalid_token", client_ip)
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid cloud token")
    
    # Check if account is locked (too many failed attempts)
    if user.is_locked:
        await log_activity(db, user.id, "login_failed_locked", client_ip)
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail="Account locked due to too many failed attempts. Contact admin."
        )
    
    # Check suspension
    if not user.is_active:
        user.login_attempts_today = (user.login_attempts_today or 0) + 1
        user.last_failed_login_at = datetime.utcnow()
        
        # Lock after 5 failed attempts
        if user.login_attempts_today >= 5:
            user.is_locked = True
            await log_activity(db, user.id, "account_locked", client_ip, details={"reason": "5_failed_attempts"})
        
        await log_activity(db, user.id, "login_failed_suspended", client_ip)
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail=f"Account suspended: {user.suspension_reason or 'Contact admin'}"
        )
    
    # Check expiration - allow DRY RUN mode for expired
    if user.expires_at < datetime.utcnow():
        # Mark as expired but allow limited access
        user.trading_mode = "DRY_RUN"
        await log_activity(db, user.id, "login_expired_dry_run", client_ip)
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail="Subscription expired. Pay USDT to renew."
        )
    
    # Check cloud instance
    if user.binding_locked and user.bound_cloud_instance:
        if user.bound_cloud_instance != CLOUD_INSTANCE_ID:
            await log_activity(
                db, user.id, "login_failed_wrong_instance", 
                client_ip,
                details={"attempted_instance": CLOUD_INSTANCE_ID, "bound_instance": user.bound_cloud_instance}
            )
            await db.commit()
            raise HTTPException(
                status_code=403,
                detail="Access denied. Token is bound to a different cloud instance."
            )
    
    # First login - needs email verification
    if not user.email_verified:
        return TokenLoginResponse(
            requires_email_verification=True,
            requires_device_verification=False,
            email_hint=None,
            message="First login. Please enter your email to verify."
        )
    
    # Check IP changes limit (2 per day)
    if user.last_ip_change_date:
        if user.last_ip_change_date.date() == datetime.utcnow().date():
            if user.ip_changes_today >= 2 and client_ip != user.last_login_ip:
                return TokenLoginResponse(
                    requires_email_verification=False,
                    requires_device_verification=True,
                    email_hint=user.email[:3] + "***" + user.email[-10:],
                    message="Too many IP changes. Email verification required."
                )
    
    # Check if different device
    # (Device verification would be handled client-side, flagged here)
    
    # All checks passed - login success
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = client_ip
    
    # Update IP history
    ips = user.login_ips or []
    if client_ip not in ips:
        ips.insert(0, client_ip)
        user.login_ips = ips[:20]  # Keep last 20
        
        # Track IP change
        if user.last_ip_change_date and user.last_ip_change_date.date() == datetime.utcnow().date():
            user.ip_changes_today += 1
        else:
            user.ip_changes_today = 1
            user.last_ip_change_date = datetime.utcnow()
    
    await log_activity(db, user.id, "login_success", client_ip)
    await db.commit()
    
    return TokenLoginResponse(
        requires_email_verification=False,
        requires_device_verification=False,
        email_hint=None,
        message="Login successful"
    )


@router.post("/request-email-code")
async def request_email_code(
    data: EmailInputRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 2a: Request email verification code.
    Sends 6-digit code to email.
    """
    from app.services.email_service import send_verification_email
    
    result = await db.execute(
        select(CloudUser).where(CloudUser.token == data.token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Check if locked
    if user.is_locked:
        raise HTTPException(status_code=403, detail="Account locked. Contact admin.")
    
    # Generate code
    code = generate_verification_code()
    code_hash = hash_code(code)
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    # Store verification
    verification = EmailVerification(
        cloud_user_id=user.id,
        email=data.email.lower(),
        code_hash=code_hash,
        purpose="first_login" if not user.email_verified else "device_change",
        expires_at=expires_at
    )
    db.add(verification)
    
    # Send email
    await send_verification_email(data.email, code)
    
    await log_activity(
        db, user.id, "email_code_requested", 
        get_client_ip(request),
        details={"email": data.email}
    )
    await db.commit()
    
    return {
        "ok": True,
        "message": f"Verification code sent to {data.email}",
        "expires_in_seconds": 300
    }


@router.post("/verify-email-code", response_model=AuthSuccessResponse)
async def verify_email_code(
    data: VerifyCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 2b: Verify email code and complete login.
    """
    result = await db.execute(
        select(CloudUser).where(CloudUser.token == data.token)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Find valid verification
    code_hash = hash_code(data.code)
    verif_result = await db.execute(
        select(EmailVerification).where(
            and_(
                EmailVerification.cloud_user_id == user.id,
                EmailVerification.email == data.email.lower(),
                EmailVerification.code_hash == code_hash,
                EmailVerification.used == False,
                EmailVerification.expires_at > datetime.utcnow()
            )
        )
    )
    verification = verif_result.scalar_one_or_none()
    
    if not verification:
        # Check for expired or wrong code
        await log_activity(
            db, user.id, "email_code_failed", 
            get_client_ip(request),
            details={"email": data.email}
        )
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    
    # Rate limit check
    if verification.attempts >= 3:
        raise HTTPException(status_code=429, detail="Too many attempts. Request new code.")
    
    verification.attempts += 1
    
    # Mark verification as used
    verification.used = True
    
    # Update user
    client_ip = get_client_ip(request)
    
    if not user.email_verified:
        # First login - bind everything
        user.email = data.email.lower()
        user.email_verified = True
        user.bound_cloud_instance = CLOUD_INSTANCE_ID
        user.bound_ip = client_ip
        user.binding_locked = True
    
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = client_ip
    
    await log_activity(
        db, user.id, "email_verified_login", 
        client_ip,
        details={"email": data.email}
    )
    await db.commit()
    
    # Calculate days remaining
    days_remaining = (user.expires_at - datetime.utcnow()).days
    
    return AuthSuccessResponse(
        access_token=user.token,  # Token itself is the access token
        user={
            "id": str(user.id),
            "email": user.email,
            "plan": user.plan,
            "telegram": user.telegram
        },
        plan=user.plan,
        days_remaining=max(0, days_remaining),
        dashboard_url="/dashboard"
    )


# ============================================================
# HEARTBEAT (LICENSE GUARDIAN)
# ============================================================

@router.post("/heartbeat")
async def send_heartbeat(
    data: HeartbeatRequest,
    request: Request,
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Heartbeat endpoint - called every 20 seconds.
    Tracks device_id, IP, browser fingerprint, cloud instance.
    """
    client_ip = get_client_ip(request)
    
    # Check device binding
    if user.binding_locked and user.bound_device_id:
        if user.bound_device_id != data.device_id:
            # Different device - flag as suspicious
            user.is_suspicious = True
            await log_activity(
                db, user.id, "abuse_detected",
                client_ip,
                details={"reason": "device_mismatch", "expected": user.bound_device_id, "got": data.device_id}
            )
            await db.commit()
            raise HTTPException(
                status_code=403,
                detail="Device mismatch. Email verification required."
            )
    else:
        # First heartbeat - bind device
        user.bound_device_id = data.device_id
        if data.browser_fingerprint:
            user.bound_browser_fingerprint = data.browser_fingerprint
    
    # Record heartbeat
    heartbeat = CloudHeartbeat(
        cloud_user_id=user.id,
        ip_address=client_ip,
        device_id=data.device_id,
        browser_fingerprint=data.browser_fingerprint,
        cloud_instance_id=CLOUD_INSTANCE_ID
    )
    db.add(heartbeat)
    
    # Update user's last heartbeat
    user.last_heartbeat_at = datetime.utcnow()
    
    # Clean old heartbeats (keep last 20)
    old_heartbeats = await db.execute(
        select(CloudHeartbeat)
        .where(CloudHeartbeat.cloud_user_id == user.id)
        .order_by(CloudHeartbeat.timestamp.desc())
        .offset(20)
    )
    for old in old_heartbeats.scalars():
        await db.delete(old)
    
    await db.commit()
    
    return {
        "ok": True,
        "server_time": datetime.utcnow().isoformat(),
        "next_heartbeat_ms": 20000
    }


# ============================================================
# USER INFO & SETTINGS
# ============================================================

@router.get("/me", response_model=CloudUserResponse)
async def get_cloud_user(user: CloudUser = Depends(get_current_cloud_user)):
    """Get current cloud user info"""
    days_remaining = (user.expires_at - datetime.utcnow()).days
    
    return CloudUserResponse(
        email=user.email,
        plan=user.plan,
        expires_at=user.expires_at.isoformat(),
        days_remaining=max(0, days_remaining),
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None
    )


@router.get("/settings")
async def get_bot_settings(
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Get bot trading settings for cloud user"""
    # Return default settings based on plan
    plan_settings = {
        "STANDARD": {
            "max_trades_per_hour": 7,
            "max_open_positions": 5,
            "min_confidence_score": 75.0,
            "mode": "DRY_RUN"
        },
        "PRO": {
            "max_trades_per_hour": 12,
            "max_open_positions": 8,
            "min_confidence_score": 70.0,
            "mode": "LIVE"
        },
        "ELITE": {
            "max_trades_per_hour": 18,
            "max_open_positions": 10,
            "min_confidence_score": 67.0,
            "mode": "LIVE"
        }
    }
    
    return {
        **plan_settings.get(user.plan, plan_settings["STANDARD"]),
        "plan": user.plan,
        "engine_profile": user.plan
    }
