"""
Sol Sniper Bot PRO - Cloud Admin Routes
Admin surveillance, user management, and monitoring.
"""
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.models.models import (
    CloudUser, CloudHeartbeat, CloudActivityLog, 
    EmailVerification, AdminToken
)

router = APIRouter(prefix="/cloud-admin", tags=["Cloud Admin"])
security = HTTPBearer(auto_error=False)


# ============================================================
# SCHEMAS
# ============================================================

class CreateCloudUserRequest(BaseModel):
    email: EmailStr
    plan: str  # STANDARD, PRO, ELITE
    telegram: Optional[str] = None
    wallet: Optional[str] = None

class CloudUserAdminResponse(BaseModel):
    id: str
    email: str
    plan: str
    token: str
    is_active: bool
    email_verified: bool
    expires_at: str
    days_remaining: int
    last_login_at: Optional[str]
    last_login_ip: Optional[str]
    is_suspicious: bool
    suspension_reason: Optional[str]
    bound_device_id: Optional[str]
    bound_cloud_instance: Optional[str]
    ip_changes_today: int

class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    expired_users: int
    suspended_users: int
    suspicious_users: int
    plan_distribution: dict
    recent_logins: int
    heartbeats_last_hour: int


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


# ============================================================
# ADMIN AUTH DEPENDENCY
# ============================================================

async def get_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> AdminToken:
    """Validate admin master token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Admin token required")
    
    token = credentials.credentials
    
    result = await db.execute(
        select(AdminToken).where(
            and_(
                AdminToken.token == token,
                AdminToken.is_active == True
            )
        )
    )
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    
    # Update last used
    admin.last_used_at = datetime.utcnow()
    await db.commit()
    
    return admin


# ============================================================
# DASHBOARD STATS
# ============================================================

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics"""
    now = datetime.utcnow()
    
    # Total users
    total_result = await db.execute(select(func.count(CloudUser.id)))
    total_users = total_result.scalar() or 0
    
    # Active users (not expired, not suspended)
    active_result = await db.execute(
        select(func.count(CloudUser.id)).where(
            and_(
                CloudUser.is_active == True,
                CloudUser.expires_at > now
            )
        )
    )
    active_users = active_result.scalar() or 0
    
    # Expired users
    expired_result = await db.execute(
        select(func.count(CloudUser.id)).where(CloudUser.expires_at <= now)
    )
    expired_users = expired_result.scalar() or 0
    
    # Suspended users
    suspended_result = await db.execute(
        select(func.count(CloudUser.id)).where(CloudUser.is_active == False)
    )
    suspended_users = suspended_result.scalar() or 0
    
    # Suspicious users
    suspicious_result = await db.execute(
        select(func.count(CloudUser.id)).where(CloudUser.is_suspicious == True)
    )
    suspicious_users = suspicious_result.scalar() or 0
    
    # Plan distribution
    plan_result = await db.execute(
        select(CloudUser.plan, func.count(CloudUser.id)).group_by(CloudUser.plan)
    )
    plan_distribution = {row[0]: row[1] for row in plan_result.fetchall()}
    
    # Recent logins (last 24h)
    login_result = await db.execute(
        select(func.count(CloudActivityLog.id)).where(
            and_(
                CloudActivityLog.action == "login_success",
                CloudActivityLog.timestamp > now - timedelta(hours=24)
            )
        )
    )
    recent_logins = login_result.scalar() or 0
    
    # Heartbeats last hour
    heartbeat_result = await db.execute(
        select(func.count(CloudHeartbeat.id)).where(
            CloudHeartbeat.timestamp > now - timedelta(hours=1)
        )
    )
    heartbeats_last_hour = heartbeat_result.scalar() or 0
    
    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        expired_users=expired_users,
        suspended_users=suspended_users,
        suspicious_users=suspicious_users,
        plan_distribution=plan_distribution,
        recent_logins=recent_logins,
        heartbeats_last_hour=heartbeats_last_hour
    )


# ============================================================
# USER MANAGEMENT
# ============================================================

@router.get("/users")
async def list_cloud_users(
    status: Optional[str] = None,  # active, expired, suspended, suspicious
    plan: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all cloud users with filtering"""
    query = select(CloudUser)
    
    now = datetime.utcnow()
    
    if status == "active":
        query = query.where(and_(CloudUser.is_active == True, CloudUser.expires_at > now))
    elif status == "expired":
        query = query.where(CloudUser.expires_at <= now)
    elif status == "suspended":
        query = query.where(CloudUser.is_active == False)
    elif status == "suspicious":
        query = query.where(CloudUser.is_suspicious == True)
    
    if plan:
        query = query.where(CloudUser.plan == plan.upper())
    
    query = query.order_by(CloudUser.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [
        CloudUserAdminResponse(
            id=str(u.id),
            email=u.email,
            plan=u.plan,
            token=u.token,
            is_active=u.is_active,
            email_verified=u.email_verified,
            expires_at=u.expires_at.isoformat(),
            days_remaining=max(0, (u.expires_at - now).days),
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            last_login_ip=u.last_login_ip,
            is_suspicious=u.is_suspicious,
            suspension_reason=u.suspension_reason,
            bound_device_id=u.bound_device_id,
            bound_cloud_instance=u.bound_cloud_instance,
            ip_changes_today=u.ip_changes_today
        )
        for u in users
    ]


@router.post("/users", response_model=CloudUserAdminResponse)
async def create_cloud_user(
    data: CreateCloudUserRequest,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create new cloud user (after USDT payment)"""
    # Check if email already exists
    existing = await db.execute(
        select(CloudUser).where(CloudUser.email == data.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate plan
    if data.plan.upper() not in ["STANDARD", "PRO", "ELITE"]:
        raise HTTPException(status_code=400, detail="Invalid plan. Use STANDARD, PRO, or ELITE")
    
    # Generate token
    token = generate_cloud_token(data.plan)
    
    # Create user with 30-day subscription
    user = CloudUser(
        email=data.email.lower(),
        plan=data.plan.upper(),
        token=token,
        telegram=data.telegram,
        wallet=data.wallet,
        expires_at=datetime.utcnow() + timedelta(days=30),
        is_active=True
    )
    db.add(user)
    
    # Log activity
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="activation",
        details={"plan": data.plan, "created_by_admin": True}
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(user)
    
    # TODO: Send email with token to user
    print(f"[EMAIL] New cloud user created: {data.email} -> Token: {token}")
    
    return CloudUserAdminResponse(
        id=str(user.id),
        email=user.email,
        plan=user.plan,
        token=user.token,
        is_active=user.is_active,
        email_verified=user.email_verified,
        expires_at=user.expires_at.isoformat(),
        days_remaining=30,
        last_login_at=None,
        last_login_ip=None,
        is_suspicious=False,
        suspension_reason=None,
        bound_device_id=None,
        bound_cloud_instance=None,
        ip_changes_today=0
    )


@router.post("/users/{user_id}/renew")
async def renew_user_subscription(
    user_id: str,
    days: int = 30,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Extend user subscription by days"""
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Extend from current expiry or from now if already expired
    if user.expires_at > datetime.utcnow():
        user.expires_at = user.expires_at + timedelta(days=days)
    else:
        user.expires_at = datetime.utcnow() + timedelta(days=days)
    
    user.is_active = True
    
    # Log
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="renewal",
        details={"days_added": days, "new_expiry": user.expires_at.isoformat()}
    )
    db.add(log)
    
    await db.commit()
    
    return {
        "ok": True,
        "message": f"Subscription extended by {days} days",
        "new_expires_at": user.expires_at.isoformat()
    }


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    reason: str = "Admin action",
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend a user"""
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    user.suspension_reason = reason
    
    # Log
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="suspension",
        details={"reason": reason}
    )
    db.add(log)
    
    await db.commit()
    
    return {"ok": True, "message": "User suspended"}


@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unsuspend a user"""
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    user.suspension_reason = None
    user.is_suspicious = False
    
    await db.commit()
    
    return {"ok": True, "message": "User unsuspended"}


@router.post("/users/{user_id}/reset-binding")
async def reset_user_binding(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reset device/IP binding for user"""
    if not admin.can_reset_bindings:
        raise HTTPException(status_code=403, detail="No permission to reset bindings")
    
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.bound_device_id = None
    user.bound_cloud_instance = None
    user.bound_ip = None
    user.bound_browser_fingerprint = None
    user.binding_locked = False
    user.ip_changes_today = 0
    user.device_reset_at = datetime.utcnow()
    
    # Log
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="binding_reset",
        details={"reset_by_admin": True}
    )
    db.add(log)
    
    await db.commit()
    
    return {"ok": True, "message": "Binding reset. User must re-verify on next login."}


@router.post("/users/{user_id}/change-plan")
async def change_user_plan(
    user_id: str,
    new_plan: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Change user's plan"""
    if new_plan.upper() not in ["STANDARD", "PRO", "ELITE"]:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_plan = user.plan
    user.plan = new_plan.upper()
    
    # Generate new token with new plan prefix
    user.token = generate_cloud_token(new_plan)
    
    # Log
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="plan_change",
        details={"old_plan": old_plan, "new_plan": new_plan.upper(), "new_token": user.token}
    )
    db.add(log)
    
    await db.commit()
    
    return {
        "ok": True,
        "new_plan": user.plan,
        "new_token": user.token
    }


@router.post("/users/{user_id}/reset-email")
async def reset_user_email(
    user_id: str,
    new_email: EmailStr,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reset user's email address"""
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if new email exists
    existing = await db.execute(
        select(CloudUser).where(CloudUser.email == new_email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already in use")
    
    old_email = user.email
    user.email = new_email.lower()
    user.email_verified = False  # Require re-verification
    
    # Log
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="email_reset",
        details={"old_email": old_email, "new_email": new_email.lower()}
    )
    db.add(log)
    
    await db.commit()
    
    return {"ok": True, "message": f"Email changed to {new_email}. User must re-verify."}


@router.post("/users/{user_id}/unlock")
async def unlock_user(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unlock a user account (after 5 failed login attempts)"""
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_locked = False
    user.login_attempts_today = 0
    
    # Log
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="account_unlocked",
        details={"unlocked_by_admin": True}
    )
    db.add(log)
    
    await db.commit()
    
    return {"ok": True, "message": "User account unlocked"}


@router.post("/users/{user_id}/force-reverify")
async def force_reverify(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Force user to re-verify email on next login"""
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.email_verified = False
    user.binding_locked = False
    
    # Log
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="force_reverify",
        details={"by_admin": True}
    )
    db.add(log)
    
    await db.commit()
    
    return {"ok": True, "message": "User must re-verify email on next login"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user permanently"""
    from app.services.email_service import send_suspension_email
    
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    email = user.email
    
    # Delete related records first
    await db.execute(
        CloudHeartbeat.__table__.delete().where(CloudHeartbeat.cloud_user_id == UUID(user_id))
    )
    await db.execute(
        CloudActivityLog.__table__.delete().where(CloudActivityLog.cloud_user_id == UUID(user_id))
    )
    await db.execute(
        EmailVerification.__table__.delete().where(EmailVerification.cloud_user_id == UUID(user_id))
    )
    
    # Delete user
    await db.delete(user)
    await db.commit()
    
    # Notify user
    await send_suspension_email(email, "Your account has been permanently deleted.")
    
    return {"ok": True, "message": f"User {email} deleted"}


@router.post("/users/{user_id}/send-activation-email")
async def send_activation_email_admin(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Re-send activation email with token to user"""
    from app.services.email_service import send_activation_email
    
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await send_activation_email(
        user.email,
        user.token,
        user.plan,
        user.expires_at.strftime("%Y-%m-%d %H:%M UTC")
    )
    
    return {"ok": True, "message": f"Activation email sent to {user.email}"}


# ============================================================
# ACTIVITY LOGS
# ============================================================

@router.get("/logs")
async def get_activity_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get activity logs"""
    if not admin.can_view_logs:
        raise HTTPException(status_code=403, detail="No permission to view logs")
    
    query = select(CloudActivityLog).order_by(CloudActivityLog.timestamp.desc())
    
    if user_id:
        query = query.where(CloudActivityLog.cloud_user_id == UUID(user_id))
    
    if action:
        query = query.where(CloudActivityLog.action == action)
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": str(log.id),
            "user_id": str(log.cloud_user_id) if log.cloud_user_id else None,
            "action": log.action,
            "ip_address": log.ip_address,
            "device_id": log.device_id,
            "timestamp": log.timestamp.isoformat(),
            "details": log.details
        }
        for log in logs
    ]


@router.get("/users/{user_id}/heartbeats")
async def get_user_heartbeats(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get last 20 heartbeats for a user"""
    result = await db.execute(
        select(CloudHeartbeat)
        .where(CloudHeartbeat.cloud_user_id == UUID(user_id))
        .order_by(CloudHeartbeat.timestamp.desc())
        .limit(20)
    )
    heartbeats = result.scalars().all()
    
    return [
        {
            "timestamp": hb.timestamp.isoformat(),
            "ip_address": hb.ip_address,
            "device_id": hb.device_id,
            "browser_fingerprint": hb.browser_fingerprint,
            "cloud_instance_id": hb.cloud_instance_id
        }
        for hb in heartbeats
    ]


# ============================================================
# KILL SWITCH
# ============================================================

@router.post("/kill-switch")
async def kill_switch(
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Disable ALL cloud users (emergency only)"""
    if not admin.can_kill_switch:
        raise HTTPException(status_code=403, detail="No permission for kill switch")
    
    await db.execute(
        CloudUser.__table__.update().values(
            is_active=False,
            suspension_reason="KILL SWITCH ACTIVATED"
        )
    )
    
    # Log
    log = CloudActivityLog(
        action="kill_switch_activated",
        details={"all_users_suspended": True}
    )
    db.add(log)
    
    await db.commit()
    
    return {"ok": True, "message": "All cloud users have been disabled"}


@router.post("/restore-all")
async def restore_all_users(
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Re-enable all users (after kill switch)"""
    if not admin.can_kill_switch:
        raise HTTPException(status_code=403, detail="No permission")
    
    await db.execute(
        CloudUser.__table__.update()
        .where(CloudUser.suspension_reason == "KILL SWITCH ACTIVATED")
        .values(is_active=True, suspension_reason=None)
    )
    
    await db.commit()
    
    return {"ok": True, "message": "All users restored"}


# ============================================================
# ADMIN TOKEN MANAGEMENT
# ============================================================

@router.post("/create-admin-token")
async def create_admin_token_endpoint(
    name: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new admin token (master only)"""
    token = generate_admin_token(name)
    
    new_admin = AdminToken(
        token=token,
        name=name
    )
    db.add(new_admin)
    await db.commit()
    
    return {
        "ok": True,
        "token": token,
        "name": name
    }


# ============================================================
# SYSTEM HEALTH & MONITORING
# ============================================================

@router.get("/system/health")
async def get_system_health(
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get overall system health status"""
    from app.services.rpc_manager import rpc_manager
    from app.services.usage_monitor import usage_monitor
    
    # RPC health
    rpc_stats = rpc_manager.get_stats()
    
    # Session stats
    session_stats = usage_monitor.get_global_stats()
    
    # Database health (simple query)
    try:
        result = await db.execute(select(func.count(CloudUser.id)))
        db_healthy = True
    except:
        db_healthy = False
    
    return {
        "status": "healthy" if rpc_stats["healthy_endpoints"] > 0 and db_healthy else "degraded",
        "rpc": {
            "tier": rpc_stats["tier"],
            "healthy_endpoints": rpc_stats["healthy_endpoints"],
            "total_endpoints": rpc_stats["total_endpoints"]
        },
        "sessions": session_stats,
        "database": "healthy" if db_healthy else "error"
    }


@router.get("/system/rpc")
async def get_rpc_health(admin: AdminToken = Depends(get_admin)):
    """Get detailed RPC health"""
    from app.services.rpc_manager import rpc_manager
    return rpc_manager.get_stats()


@router.get("/system/sessions")
async def get_all_sessions(admin: AdminToken = Depends(get_admin)):
    """Get all active cloud sessions"""
    from app.services.usage_monitor import usage_monitor
    return usage_monitor.get_all_active_sessions()


@router.post("/system/session/{session_key}/kill")
async def kill_session(
    session_key: str,
    admin: AdminToken = Depends(get_admin)
):
    """Force stop a cloud session"""
    from app.services.usage_monitor import usage_monitor
    success = await usage_monitor.stop_session(session_key)
    return {"ok": success, "message": "Session killed" if success else "Session not found"}


# ============================================================
# LICENSE MANAGEMENT
# ============================================================

@router.post("/user/{user_id}/reset-devices")
async def admin_reset_devices(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reset all devices for a user"""
    from app.services.license_service import license_service
    success, message = await license_service.reset_devices(db, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {"ok": True, "message": message}


@router.post("/user/{user_id}/renew")
async def admin_renew_subscription(
    user_id: str,
    plan: str,
    days: int = 30,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Manually renew a user's subscription"""
    from app.services.license_service import license_service
    success, message = await license_service.renew_subscription(db, user_id, plan, days)
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {"ok": True, "message": message}


@router.post("/user/{user_id}/suspend")
async def admin_suspend_user(
    user_id: str,
    reason: str = "Manual suspension by admin",
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend a user's license"""
    from app.services.license_service import license_service
    success, message = await license_service.suspend_user(
        db, user_id, reason, admin.name
    )
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {"ok": True, "message": message}


@router.post("/user/{user_id}/reactivate")
async def admin_reactivate_user(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reactivate a suspended user"""
    from app.services.license_service import license_service
    success, message = await license_service.reactivate_user(
        db, user_id, admin.name
    )
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {"ok": True, "message": message}


@router.get("/user/{user_id}/license")
async def get_user_license_info(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed license info for a user"""
    from app.services.license_service import license_service
    info = await license_service.get_license_info(db, user_id)
    
    if not info:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "license_key": info.license_key,
        "email": info.email,
        "plan": info.plan,
        "status": info.status.value,
        "max_devices": info.max_devices,
        "devices_count": len(info.devices),
        "devices": [
            {"hwid": d.hwid[:12] + "...", "ip": d.ip}
            for d in info.devices
        ],
        "created_at": info.created_at.isoformat(),
        "expires_at": info.expires_at.isoformat() if info.expires_at else None,
        "days_remaining": info.days_remaining,
        "is_lifetime": info.is_lifetime
    }


@router.post("/user/{user_id}/regenerate-license")
async def regenerate_license_key(
    user_id: str,
    admin: AdminToken = Depends(get_admin),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate a user's license key"""
    from app.services.license_service import license_service
    
    result = await db.execute(
        select(CloudUser).where(CloudUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_token = license_service.generate_license_key(user.plan)
    user.token = new_token
    await db.commit()
    
    return {"ok": True, "new_license_key": new_token}


# ============================================================
# PAYMENT & ORDER MANAGEMENT
# ============================================================

@router.get("/payments")
async def get_all_payments(
    limit: int = 50,
    admin: AdminToken = Depends(get_admin)
):
    """Get all pending and confirmed payments"""
    from app.services.usdt_payments import payment_service
    
    all_subs = payment_service.get_all_subscriptions()
    
    return {
        "subscriptions": all_subs[:limit],
        "pending_payments": len(payment_service.pending_payments),
        "confirmed_payments": len(payment_service.confirmed_payments)
    }


@router.post("/payments/approve")
async def admin_approve_payment(
    user_id: str,
    plan: str,
    admin: AdminToken = Depends(get_admin)
):
    """Manually approve a payment"""
    from app.services.usdt_payments import payment_service
    
    success = await payment_service.admin_approve_payment(
        user_id=user_id,
        plan=plan,
        admin_id=admin.name
    )
    
    return {"ok": success, "message": "Payment approved and subscription activated"}


@router.post("/payments/revoke/{user_id}")
async def admin_revoke_subscription(
    user_id: str,
    reason: str = "Revoked by admin",
    admin: AdminToken = Depends(get_admin)
):
    """Revoke a subscription"""
    from app.services.usdt_payments import payment_service
    
    success = await payment_service.admin_revoke_subscription(
        user_id=user_id,
        admin_id=admin.name,
        reason=reason
    )
    
    return {"ok": success, "message": "Subscription revoked"}


# ============================================================
# USAGE ANALYTICS
# ============================================================

@router.get("/analytics/top-consumers")
async def get_top_consumers(
    limit: int = 20,
    admin: AdminToken = Depends(get_admin)
):
    """Get top RPC consumers"""
    from app.services.rpc_manager import rpc_manager
    return rpc_manager.get_top_consumers(limit=limit)


@router.get("/analytics/sessions")
async def get_session_analytics(admin: AdminToken = Depends(get_admin)):
    """Get session analytics"""
    from app.services.usage_monitor import usage_monitor
    
    all_sessions = usage_monitor.get_all_active_sessions()
    
    # Calculate analytics
    total_scans = sum(s["tokens_scanned"] for s in all_sessions)
    total_trades = sum(s["trades_triggered"] for s in all_sessions)
    
    by_plan = {}
    for s in all_sessions:
        plan = s["plan"]
        if plan not in by_plan:
            by_plan[plan] = 0
        by_plan[plan] += 1
    
    return {
        "total_active_sessions": len(all_sessions),
        "total_scans_today": total_scans,
        "total_trades_today": total_trades,
        "sessions_by_plan": by_plan,
        "sessions": all_sessions
    }
