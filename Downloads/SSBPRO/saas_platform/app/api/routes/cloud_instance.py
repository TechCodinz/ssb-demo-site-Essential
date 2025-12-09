"""
Sol Sniper Bot PRO - Cloud Instance API Routes
Endpoints for managing and monitoring cloud trading instances.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.services.cloud_engine import cloud_engine, InstanceStatus
from app.api.routes.cloud_auth import get_current_cloud_user
from app.models.models import CloudUser, CloudActivityLog

router = APIRouter(prefix="/cloud/instance", tags=["Cloud Instance"])


# ============================================================
# SCHEMAS
# ============================================================

class StartInstanceRequest(BaseModel):
    trading_mode: str = "DRY_RUN"  # DRY_RUN or LIVE


class InstanceResponse(BaseModel):
    status: str
    started_at: Optional[str] = None
    uptime_seconds: int = 0
    tokens_scanned: int = 0
    trades_executed: int = 0
    trades_successful: int = 0
    errors_count: int = 0
    trading_mode: str = "DRY_RUN"
    last_heartbeat: Optional[str] = None


# ============================================================
# INSTANCE MANAGEMENT
# ============================================================

@router.get("/status", response_model=InstanceResponse)
async def get_instance_status(
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get current cloud instance status for user."""
    instance = cloud_engine.get_instance(str(user.id))
    
    if not instance:
        return InstanceResponse(status="stopped")
    
    return InstanceResponse(
        status=instance.status.value,
        started_at=instance.stats.started_at.isoformat() if instance.stats.started_at else None,
        uptime_seconds=instance.stats.uptime_seconds,
        tokens_scanned=instance.stats.tokens_scanned,
        trades_executed=instance.stats.trades_executed,
        trades_successful=instance.stats.trades_successful,
        errors_count=instance.stats.errors_count,
        trading_mode=instance.trading_mode,
        last_heartbeat=instance.last_heartbeat.isoformat() if instance.last_heartbeat else None
    )


@router.post("/start")
async def start_instance(
    data: StartInstanceRequest,
    request: Request,
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Start cloud trading instance for user."""
    # Check if subscription is active
    if user.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=403,
            detail="Subscription expired. Cannot start cloud instance."
        )
    
    # Check plan limits
    limits = settings.PLAN_LIMITS.get(user.plan, settings.PLAN_LIMITS["DEMO"])
    
    # Validate trading mode
    trading_mode = data.trading_mode.upper()
    if trading_mode == "LIVE" and not limits.get("live_trading"):
        trading_mode = "DRY_RUN"
    
    # Check if user is on expired plan - force DRY RUN
    if user.trading_mode == "DRY_RUN":
        trading_mode = "DRY_RUN"
    
    try:
        instance = await cloud_engine.start_instance(
            user_id=str(user.id),
            license_id=str(user.id),
            plan=user.plan,
            trading_mode=trading_mode
        )
        
        # Log activity
        log = CloudActivityLog(
            cloud_user_id=user.id,
            action="instance_started",
            ip_address=request.headers.get("x-forwarded-for", request.client.host),
            details={"trading_mode": trading_mode}
        )
        db.add(log)
        await db.commit()
        
        return {
            "ok": True,
            "status": instance.status.value,
            "trading_mode": instance.trading_mode,
            "message": f"Cloud instance started in {trading_mode} mode"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop")
async def stop_instance(
    request: Request,
    user: CloudUser = Depends(get_current_cloud_user),
    db: AsyncSession = Depends(get_db)
):
    """Stop cloud trading instance for user."""
    success = await cloud_engine.stop_instance(str(user.id))
    
    if not success:
        raise HTTPException(status_code=404, detail="No running instance found")
    
    # Log activity
    log = CloudActivityLog(
        cloud_user_id=user.id,
        action="instance_stopped",
        ip_address=request.headers.get("x-forwarded-for", request.client.host)
    )
    db.add(log)
    await db.commit()
    
    return {"ok": True, "status": "stopped", "message": "Cloud instance stopped"}


@router.get("/stats")
async def get_instance_stats(user: CloudUser = Depends(get_current_cloud_user)):
    """Get detailed statistics for user's instance."""
    instance = cloud_engine.get_instance(str(user.id))
    
    if not instance:
        return {
            "running": False,
            "stats": None
        }
    
    return {
        "running": instance.status == InstanceStatus.RUNNING,
        "stats": {
            "tokens_scanned": instance.stats.tokens_scanned,
            "trades_executed": instance.stats.trades_executed,
            "trades_successful": instance.stats.trades_successful,
            "trades_failed": instance.stats.trades_failed,
            "success_rate": round(
                instance.stats.trades_successful / instance.stats.trades_executed * 100, 2
            ) if instance.stats.trades_executed > 0 else 0,
            "errors_count": instance.stats.errors_count,
            "uptime_seconds": instance.stats.uptime_seconds,
            "last_tp": instance.stats.last_tp_at.isoformat() if instance.stats.last_tp_at else None,
            "last_sl": instance.stats.last_sl_at.isoformat() if instance.stats.last_sl_at else None,
            "started_at": instance.stats.started_at.isoformat() if instance.stats.started_at else None
        },
        "plan": instance.plan,
        "trading_mode": instance.trading_mode,
        "restart_count": instance.restart_count
    }


@router.get("/limits")
async def get_plan_limits(user: CloudUser = Depends(get_current_cloud_user)):
    """Get plan limits for current user."""
    limits = settings.PLAN_LIMITS.get(user.plan, settings.PLAN_LIMITS["DEMO"])
    
    return {
        "plan": user.plan,
        "limits": limits,
        "days_remaining": max(0, (user.expires_at - datetime.utcnow()).days),
        "trading_enabled": limits.get("live_trading", False)
    }
