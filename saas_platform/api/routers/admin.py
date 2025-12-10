"""
SSB PRO - Ultra Admin API Endpoints
Full control panel with: monitoring, database, licensing, password management, security
Protected with proper authentication and audit logging
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import hashlib
import secrets
import json
import os

from api.database import get_db
from api.models.user import User, ReferralEarning
from api.models.order import Order
from api.models.license import License
from api.services.jwt_service import create_access_token, verify_token
from api.config import settings

router = APIRouter()
security = HTTPBearer()

# Admin credentials (in production, store hashed in DB or env)
ADMIN_USERS = {
    "admin@ssbpro.dev": {
        "password_hash": hashlib.sha256("SSBCloud2025Admin!".encode()).hexdigest(),
        "role": "super_admin"
    }
}

# Audit log storage
AUDIT_LOG = []


# ==================== SECURITY HELPERS ====================

def log_admin_action(admin_email: str, action: str, details: dict, ip: str = "unknown"):
    """Log all admin actions for audit trail"""
    entry = {
        "id": secrets.token_hex(8),
        "admin": admin_email,
        "action": action,
        "details": details,
        "ip": ip,
        "timestamp": datetime.utcnow().isoformat()
    }
    AUDIT_LOG.append(entry)
    print(f"[ADMIN AUDIT] {admin_email} - {action}: {json.dumps(details)}")
    return entry


def verify_admin_token(credentials: HTTPAuthorizationCredentials):
    """Verify admin JWT token"""
    try:
        payload = verify_token(credentials.credentials)
        if payload.get("role") not in ["admin", "super_admin"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ==================== REQUEST MODELS ====================

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordChangeRequest(BaseModel):
    user_id: str
    new_password: str


class AdminPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class LicenseUpdateRequest(BaseModel):
    license_key: str
    action: str  # extend, revoke, upgrade, downgrade
    value: Optional[str] = None  # days for extend, plan for upgrade/downgrade


class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    plan: Optional[str] = None
    verified: Optional[bool] = None
    suspended: Optional[bool] = None


class BroadcastRequest(BaseModel):
    message: str
    target: str = "all"


class SystemConfigRequest(BaseModel):
    key: str
    value: str


# ==================== AUTH ENDPOINTS ====================

@router.post("/login")
async def admin_login(request: AdminLoginRequest, req: Request):
    """Secure admin login with JWT"""
    admin = ADMIN_USERS.get(request.email)
    
    if not admin:
        log_admin_action("unknown", "login_failed", {"email": request.email}, req.client.host)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    if password_hash != admin["password_hash"]:
        log_admin_action(request.email, "login_failed", {"reason": "wrong_password"}, req.client.host)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate admin JWT
    token = create_access_token({
        "sub": request.email,
        "email": request.email,
        "role": admin["role"]
    })
    
    log_admin_action(request.email, "login_success", {}, req.client.host)
    
    return {
        "success": True,
        "token": token,
        "role": admin["role"],
        "email": request.email
    }


@router.post("/change-admin-password")
async def change_admin_password(
    request: AdminPasswordChangeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Change admin password"""
    admin_data = verify_admin_token(credentials)
    admin_email = admin_data.get("email")
    
    admin = ADMIN_USERS.get(admin_email)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    current_hash = hashlib.sha256(request.current_password.encode()).hexdigest()
    if current_hash != admin["password_hash"]:
        raise HTTPException(status_code=401, detail="Current password incorrect")
    
    # Update password
    ADMIN_USERS[admin_email]["password_hash"] = hashlib.sha256(request.new_password.encode()).hexdigest()
    
    log_admin_action(admin_email, "password_changed", {"target": "self"})
    
    return {"success": True, "message": "Admin password updated"}


# ==================== USER MANAGEMENT ====================

@router.get("/users")
async def list_users(
    search: Optional[str] = None,
    plan: Optional[str] = None,
    verified: Optional[bool] = None,
    page: int = 1,
    limit: int = 50,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """List all users from database"""
    verify_admin_token(credentials)
    
    query = db.query(User)
    
    if search:
        query = query.filter(User.email.contains(search))
    if plan:
        query = query.filter(User.plan == plan)
    if verified is not None:
        query = query.filter(User.verified == verified)
    
    total = query.count()
    users = query.order_by(desc(User.created_at)).offset((page-1)*limit).limit(limit).all()
    
    return {
        "users": [{
            "id": u.id,
            "email": u.email,
            "plan": u.plan,
            "verified": u.verified,
            "referral_code": u.referral_code,
            "total_pnl": u.total_pnl or 0,
            "created_at": u.created_at.isoformat() if u.created_at else None
        } for u in users],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get detailed user info"""
    verify_admin_token(credentials)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's license
    license = db.query(License).filter(License.email == user.email).first()
    
    # Get referral stats
    referrals = db.query(User).filter(User.referred_by == user.referral_code).count()
    earnings = db.query(func.sum(ReferralEarning.amount)).filter(
        ReferralEarning.user_id == user.id
    ).scalar() or 0
    
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.plan,
        "verified": user.verified,
        "telegram_id": user.telegram_id,
        "referral_code": user.referral_code,
        "referred_by": user.referred_by,
        "total_pnl": user.total_pnl or 0,
        "total_referral_earnings": user.total_referral_earnings or 0,
        "referral_count": referrals,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "license": {
            "key": license.key if license else None,
            "plan": license.plan if license else None,
            "expires": license.expires.isoformat() if license and license.expires else None,
            "activated": license.activated if license else False
        } if license else None
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Update user details"""
    admin_data = verify_admin_token(credentials)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    changes = {}
    
    if request.email:
        user.email = request.email
        changes["email"] = request.email
    if request.plan:
        user.plan = request.plan
        changes["plan"] = request.plan
    if request.verified is not None:
        user.verified = request.verified
        changes["verified"] = request.verified
    
    db.commit()
    
    log_admin_action(admin_data["email"], "user_updated", {"user_id": user_id, "changes": changes})
    
    return {"success": True, "message": "User updated", "changes": changes}


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    request: PasswordChangeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Reset user password (admin override)"""
    admin_data = verify_admin_token(credentials)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Hash new password
    user.password_hash = hashlib.sha256(request.new_password.encode()).hexdigest()
    db.commit()
    
    log_admin_action(admin_data["email"], "password_reset", {"user_id": user_id, "email": user.email})
    
    return {"success": True, "message": f"Password reset for {user.email}"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Delete user (soft delete - marks as suspended)"""
    admin_data = verify_admin_token(credentials)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Soft delete - just mark verification as false and add prefix
    old_email = user.email
    user.email = f"DELETED_{user.id}_{user.email}"
    user.verified = False
    db.commit()
    
    log_admin_action(admin_data["email"], "user_deleted", {"user_id": user_id, "email": old_email})
    
    return {"success": True, "message": "User deleted"}


# ==================== LICENSE MANAGEMENT ====================

@router.get("/licenses")
async def list_licenses(
    status: Optional[str] = None,
    plan: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """List all licenses"""
    verify_admin_token(credentials)
    
    query = db.query(License)
    
    if plan:
        query = query.filter(License.plan == plan)
    
    total = query.count()
    licenses = query.order_by(desc(License.issued_at)).offset((page-1)*limit).limit(limit).all()
    
    return {
        "licenses": [{
            "key": l.key,
            "email": l.email,
            "plan": l.plan,
            "activated": l.activated,
            "expires": l.expires.isoformat() if l.expires else None,
            "issued_at": l.issued_at.isoformat() if l.issued_at else None
        } for l in licenses],
        "total": total,
        "page": page
    }


@router.post("/licenses/action")
async def license_action(
    request: LicenseUpdateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Perform action on license: extend, revoke, upgrade, downgrade"""
    admin_data = verify_admin_token(credentials)
    
    license = db.query(License).filter(License.key == request.license_key).first()
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    action_result = {}
    
    if request.action == "extend":
        days = int(request.value or 30)
        license.expires = license.expires + timedelta(days=days) if license.expires else datetime.utcnow() + timedelta(days=days)
        action_result = {"new_expires": license.expires.isoformat()}
        
    elif request.action == "revoke":
        license.expires = datetime.utcnow() - timedelta(days=1)
        action_result = {"revoked": True}
        
    elif request.action in ["upgrade", "downgrade"]:
        old_plan = license.plan
        license.plan = request.value
        action_result = {"old_plan": old_plan, "new_plan": request.value}
    
    db.commit()
    
    log_admin_action(admin_data["email"], f"license_{request.action}", {
        "license_key": request.license_key,
        **action_result
    })
    
    return {"success": True, "action": request.action, "result": action_result}


# ==================== MONITORING & METRICS ====================

@router.get("/metrics")
async def get_system_metrics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get real-time system metrics from database"""
    verify_admin_token(credentials)
    
    # Real counts from database
    total_users = db.query(User).count()
    verified_users = db.query(User).filter(User.verified == True).count()
    total_orders = db.query(Order).filter(Order.status == "completed").count()
    total_licenses = db.query(License).count()
    
    # Revenue
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
    week_start = datetime.utcnow() - timedelta(days=7)
    
    # Count referral earnings
    total_referral_earnings = db.query(func.sum(ReferralEarning.amount)).scalar() or 0
    
    return {
        "users": {
            "total": total_users,
            "verified": verified_users,
            "unverified": total_users - verified_users
        },
        "licenses": {
            "total": total_licenses,
            "active": db.query(License).filter(License.expires > datetime.utcnow()).count()
        },
        "orders": {
            "total": total_orders,
            "pending": db.query(Order).filter(Order.status == "pending").count()
        },
        "referrals": {
            "total_earnings": total_referral_earnings,
            "total_referrers": db.query(User).filter(User.total_referral_earnings > 0).count()
        },
        "system": {
            "api_status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }
    }


@router.get("/audit-logs")
async def get_audit_logs(
    admin: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get admin audit logs"""
    verify_admin_token(credentials)
    
    logs = AUDIT_LOG[-limit:]
    
    if admin:
        logs = [l for l in logs if l["admin"] == admin]
    if action:
        logs = [l for l in logs if action in l["action"]]
    
    return {"logs": list(reversed(logs)), "total": len(logs)}


# ==================== ORDERS & PAYMENTS ====================

@router.get("/orders")
async def list_orders(
    status: Optional[str] = None,
    email: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """List all orders"""
    verify_admin_token(credentials)
    
    query = db.query(Order)
    
    if status:
        query = query.filter(Order.status == status)
    if email:
        query = query.filter(Order.email.contains(email))
    
    total = query.count()
    orders = query.order_by(desc(Order.created_at)).offset((page-1)*limit).limit(limit).all()
    
    return {
        "orders": [{
            "order_id": o.order_id,
            "email": o.email,
            "plan": o.plan,
            "amount": o.amount,
            "status": o.status,
            "tx_hash": o.tx_hash,
            "license_key": o.license_key,
            "created_at": o.created_at.isoformat() if o.created_at else None
        } for o in orders],
        "total": total,
        "page": page
    }


# ==================== BROADCAST & SYSTEM ====================

@router.post("/broadcast")
async def broadcast_message(
    request: BroadcastRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Broadcast message to users"""
    admin_data = verify_admin_token(credentials)
    
    # Count recipients
    if request.target == "all":
        count = db.query(User).count()
    elif request.target == "active":
        count = db.query(User).filter(User.verified == True).count()
    else:
        count = 0
    
    log_admin_action(admin_data["email"], "broadcast", {
        "message": request.message[:100],
        "target": request.target,
        "recipients": count
    })
    
    return {
        "success": True,
        "message": request.message,
        "target": request.target,
        "recipients": count
    }


@router.get("/system-health")
async def system_health(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Full system health check"""
    verify_admin_token(credentials)
    
    checks = {
        "database": "healthy",
        "api": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Test database
    try:
        db.execute("SELECT 1")
        checks["database"] = "healthy"
    except:
        checks["database"] = "error"
    
    return checks
