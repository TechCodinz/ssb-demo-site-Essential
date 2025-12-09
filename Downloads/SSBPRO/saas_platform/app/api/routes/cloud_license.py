"""
Sol Sniper Bot PRO - License API Routes
API endpoints for license management, device control, and user dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.api.routes.cloud_auth import get_current_cloud_user
from app.models.models import CloudUser
from app.core.database import get_db
from app.services.license_service import license_service, LicenseStatus, PLAN_DEVICE_LIMITS
from app.services.usage_monitor import usage_monitor
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/cloud/license", tags=["License"])


# ============================================================
# SCHEMAS
# ============================================================

class LicenseValidateRequest(BaseModel):
    license_key: str
    email: str
    hwid: str


class LicenseValidateResponse(BaseModel):
    valid: bool
    message: str
    cloud_token: Optional[str]
    plan: Optional[str]
    expires_at: Optional[str]


class LicenseInfoResponse(BaseModel):
    license_key: str
    email: str
    plan: str
    status: str
    max_devices: int
    devices_used: int
    created_at: str
    expires_at: Optional[str]
    days_remaining: int
    is_lifetime: bool


class DeviceResponse(BaseModel):
    hwid: str
    ip: str
    added_at: str
    approved: bool


class DeviceApprovalRequest(BaseModel):
    approval_token: str


class SessionStartRequest(BaseModel):
    device_id: str = ""


class SessionStartResponse(BaseModel):
    success: bool
    session_key: Optional[str]
    message: str


class SessionStatsResponse(BaseModel):
    status: str
    started_at: str
    runtime_hours: float
    tokens_scanned: int
    filters_passed: int
    filters_blocked: int
    trades_triggered: int
    errors: int
    avg_confidence: float


# ============================================================
# LICENSE VALIDATION (FOR DESKTOP/CLOUD)
# ============================================================

@router.post("/validate", response_model=LicenseValidateResponse)
async def validate_license(
    request: LicenseValidateRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate license key + email + HWID combination.
    Used by both desktop app and cloud engine.
    """
    ip = req.client.host if req.client else ""
    
    valid, message, cloud_token = await license_service.validate_license(
        db=db,
        license_key=request.license_key,
        hwid=request.hwid,
        email=request.email,
        ip=ip
    )
    
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message
        )
    
    # Get user info
    from sqlalchemy import select
    result = await db.execute(
        select(CloudUser).where(CloudUser.token == request.license_key)
    )
    user = result.scalar_one_or_none()
    
    return LicenseValidateResponse(
        valid=True,
        message=message,
        cloud_token=cloud_token,
        plan=user.plan if user else None,
        expires_at=user.expires_at.isoformat() if user and user.expires_at else None
    )


# ============================================================
# LICENSE INFO
# ============================================================

@router.get("/info", response_model=LicenseInfoResponse)
async def get_license_info(
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's license information"""
    info = await license_service.get_license_info(db, str(user.id))
    
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found"
        )
    
    return LicenseInfoResponse(
        license_key=info.license_key,
        email=info.email,
        plan=info.plan,
        status=info.status.value,
        max_devices=info.max_devices,
        devices_used=len(info.devices),
        created_at=info.created_at.isoformat(),
        expires_at=info.expires_at.isoformat() if info.expires_at else None,
        days_remaining=info.days_remaining,
        is_lifetime=info.is_lifetime
    )


@router.get("/status")
async def get_license_status(user: CloudUser = Depends(get_current_cloud_user)):
    """Get quick license status for dashboard"""
    days_remaining = 0
    is_lifetime = False
    
    if user.plan == "ELITE":
        is_lifetime = True
        days_remaining = -1
    elif user.expires_at:
        delta = user.expires_at - datetime.utcnow()
        days_remaining = max(0, delta.days)
    
    return {
        "plan": user.plan,
        "is_active": user.is_active,
        "days_remaining": days_remaining,
        "is_lifetime": is_lifetime,
        "expires_at": user.expires_at.isoformat() if user.expires_at else None,
        "trading_mode": user.trading_mode
    }


# ============================================================
# DEVICE MANAGEMENT
# ============================================================

@router.get("/devices", response_model=List[DeviceResponse])
async def get_devices(
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of registered devices"""
    devices = await license_service.get_user_devices(db, str(user.id))
    return [DeviceResponse(**d) for d in devices]


@router.post("/devices/approve")
async def approve_device(
    request: DeviceApprovalRequest,
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending device"""
    success, message = await license_service.approve_device(
        db=db,
        user_id=str(user.id),
        approval_token=request.approval_token
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"ok": True, "message": message}


@router.post("/devices/deny")
async def deny_device(
    request: DeviceApprovalRequest,
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Deny a pending device"""
    success, message = await license_service.deny_device(
        db=db,
        user_id=str(user.id),
        approval_token=request.approval_token
    )
    
    return {"ok": success, "message": message}


@router.post("/devices/reset")
async def request_device_reset(
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Request HWID reset (requires admin approval for security)"""
    # For security, device reset requests go to admin
    # User can only request, not self-reset
    return {
        "ok": True,
        "message": "Device reset request submitted. Contact support for approval."
    }


# ============================================================
# CLOUD SESSION MANAGEMENT
# ============================================================

@router.post("/session/start", response_model=SessionStartResponse)
async def start_session(
    request: SessionStartRequest,
    req: Request,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Start a new cloud engine session"""
    # Check if license is valid
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"License suspended: {user.suspension_reason or 'Contact support'}"
        )
    
    if user.expires_at and user.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="License expired. Please renew to continue."
        )
    
    ip = req.client.host if req.client else ""
    
    success, result = await usage_monitor.start_session(
        user_id=str(user.id),
        email=user.email,
        plan=user.plan,
        ip=ip,
        device_id=request.device_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=result
        )
    
    return SessionStartResponse(
        success=True,
        session_key=result,
        message="Session started successfully"
    )


@router.post("/session/stop")
async def stop_session(
    session_key: str,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Stop a cloud engine session"""
    success = await usage_monitor.stop_session(session_key)
    
    return {"ok": success, "message": "Session stopped" if success else "Session not found"}


@router.post("/session/heartbeat")
async def session_heartbeat(
    session_key: str,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Send session heartbeat to keep alive"""
    success = await usage_monitor.heartbeat(session_key)
    return {"ok": success}


@router.get("/session/stats")
async def get_session_stats(
    session_key: str,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get current session statistics"""
    stats = usage_monitor.get_session_stats(session_key)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return stats


@router.get("/session/active")
async def get_active_sessions(user: CloudUser = Depends(get_current_cloud_user)):
    """Get user's active sessions"""
    sessions = usage_monitor.get_user_sessions(str(user.id))
    
    return [
        {
            "status": s.status.value,
            "started_at": s.started_at.isoformat(),
            "tokens_scanned": s.tokens_scanned,
            "trades_triggered": s.trades_triggered
        }
        for s in sessions
    ]


# ============================================================
# USER DASHBOARD DATA
# ============================================================

@router.get("/dashboard")
async def get_dashboard_data(
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all dashboard data in one call"""
    # License info
    info = await license_service.get_license_info(db, str(user.id))
    
    # Active sessions
    sessions = usage_monitor.get_user_sessions(str(user.id))
    active_session = sessions[0] if sessions else None
    
    # Today's metrics
    today_metrics = {
        "tokens_scanned": 0,
        "filters_passed": 0,
        "trades_triggered": 0,
        "avg_confidence": 0.0
    }
    
    if active_session:
        today_metrics = {
            "tokens_scanned": active_session.tokens_scanned,
            "filters_passed": active_session.filters_passed,
            "trades_triggered": active_session.trades_triggered,
            "avg_confidence": round(active_session.avg_confidence, 2)
        }
    
    # HWID info
    devices = await license_service.get_user_devices(db, str(user.id))
    
    return {
        "user": {
            "email": user.email,
            "plan": user.plan,
            "telegram": user.telegram
        },
        "license": {
            "status": info.status.value if info else "unknown",
            "expires_at": info.expires_at.isoformat() if info and info.expires_at else None,
            "days_remaining": info.days_remaining if info else 0,
            "is_lifetime": info.is_lifetime if info else False
        },
        "session": {
            "active": active_session is not None,
            "status": active_session.status.value if active_session else "stopped",
            "runtime_hours": round(
                (datetime.utcnow() - active_session.started_at).total_seconds() / 3600, 2
            ) if active_session else 0
        },
        "metrics": today_metrics,
        "devices": {
            "max": PLAN_DEVICE_LIMITS.get(user.plan, 1),
            "used": len(devices)
        }
    }


# ============================================================
# BILLING INFO
# ============================================================

@router.get("/billing")
async def get_billing_info(
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Get billing information for renewal"""
    from app.services.usdt_payments import payment_service, PLAN_PRICES
    
    # Get payment history
    history = payment_service.get_payment_history(str(user.id))
    
    # Get renewal info
    renewal_address = None
    if user.plan != "ELITE":  # ELITE is lifetime
        payment = payment_service.generate_payment_address(str(user.id), user.plan)
        renewal_address = payment.address
    
    return {
        "plan": user.plan,
        "price": PLAN_PRICES.get(user.plan, 0),
        "expires_at": user.expires_at.isoformat() if user.expires_at else None,
        "renewal_address": renewal_address,
        "is_lifetime": user.plan == "ELITE",
        "payment_history": history[:10]  # Last 10 payments
    }
