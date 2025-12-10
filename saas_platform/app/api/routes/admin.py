"""
Sol Sniper Bot PRO - Admin Routes
User management and system administration
"""
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel

from app.core.database import get_db
from app.models.models import (
    User, Plan, Subscription, BotInstance, BotLog,
    SubscriptionStatus, BillingType, BotStatus
)
from app.api.routes.auth import get_current_admin


router = APIRouter(prefix="/admin", tags=["Admin"])


# ============================================================
# SCHEMAS
# ============================================================

class OverridePlanRequest(BaseModel):
    user_id: str
    plan_id: str


class ActivateLifetimeRequest(BaseModel):
    user_id: str
    plan_id: str


# ============================================================
# ROUTES
# ============================================================

@router.get("/users")
async def list_users(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all users"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "telegram": u.telegram_username,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat()
        }
        for u in users
    ]


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed user info including subscription and bot status"""
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get subscription
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )
    sub = result.scalar_one_or_none()
    
    # Get bot instance
    result = await db.execute(
        select(BotInstance).where(BotInstance.user_id == user.id)
    )
    bot = result.scalar_one_or_none()
    
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "telegram": user.telegram_username,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat()
        },
        "subscription": {
            "plan_id": sub.plan_id if sub else None,
            "status": sub.status.value if sub else None,
            "billing_type": sub.billing_type.value if sub else None,
            "created_at": sub.created_at.isoformat() if sub else None
        } if sub else None,
        "bot": {
            "status": bot.status.value if bot else None,
            "mode": bot.mode.value if bot else None,
            "engine_profile": bot.engine_profile if bot else None
        } if bot else None
    }


@router.post("/users/{user_id}/block")
async def block_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Block a user"""
    await db.execute(
        update(User).where(User.id == UUID(user_id)).values(is_active=False)
    )
    await db.commit()
    return {"success": True, "message": "User blocked"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unblock a user"""
    await db.execute(
        update(User).where(User.id == UUID(user_id)).values(is_active=True)
    )
    await db.commit()
    return {"success": True, "message": "User unblocked"}


@router.post("/override-plan")
async def override_plan(
    data: OverridePlanRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Override a user's plan tier"""
    # Get plan
    result = await db.execute(select(Plan).where(Plan.id == data.plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    user_id = UUID(data.user_id)
    
    # Update or create subscription
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )
    sub = result.scalar_one_or_none()
    
    if sub:
        sub.plan_id = data.plan_id
        sub.updated_at = datetime.utcnow()
    else:
        sub = Subscription(
            user_id=user_id,
            plan_id=data.plan_id,
            billing_type=BillingType.LIFETIME,
            status=SubscriptionStatus.ACTIVE
        )
        db.add(sub)
    
    # Update bot instance
    result = await db.execute(
        select(BotInstance).where(BotInstance.user_id == user_id)
    )
    bot = result.scalar_one_or_none()
    if bot:
        bot.engine_profile = plan.engine_profile
        bot.max_trades_per_hour = plan.max_trades_per_hour
        bot.max_open_positions = plan.max_open_positions
        bot.min_confidence_score = plan.min_confidence_score
    
    await db.commit()
    return {"success": True, "message": f"Plan overridden to {plan.name}"}


@router.post("/activate-lifetime")
async def activate_lifetime(
    data: ActivateLifetimeRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Manually activate lifetime subscription for a user"""
    return await override_plan(
        OverridePlanRequest(user_id=data.user_id, plan_id=data.plan_id),
        admin, db
    )


@router.post("/reset-subscription/{user_id}")
async def reset_subscription(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Cancel/reset a user's subscription"""
    await db.execute(
        update(Subscription)
        .where(Subscription.user_id == UUID(user_id))
        .values(status=SubscriptionStatus.CANCELLED)
    )
    await db.commit()
    return {"success": True, "message": "Subscription reset"}


@router.get("/logs/{user_id}")
async def get_user_logs(
    user_id: str,
    limit: int = 200,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get logs for a specific user's bot"""
    result = await db.execute(
        select(BotInstance).where(BotInstance.user_id == UUID(user_id))
    )
    bot = result.scalar_one_or_none()
    
    if not bot:
        return []
    
    result = await db.execute(
        select(BotLog)
        .where(BotLog.bot_instance_id == bot.id)
        .order_by(BotLog.timestamp.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    return [
        {
            "timestamp": log.timestamp.isoformat(),
            "level": log.level.value,
            "message": log.message
        }
        for log in logs
    ]


@router.get("/stats")
async def get_system_stats(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get system-wide statistics"""
    from sqlalchemy import func
    
    # Count users
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar()
    
    # Count active subscriptions
    result = await db.execute(
        select(func.count(Subscription.id)).where(
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )
    active_subs = result.scalar()
    
    # Count running bots
    result = await db.execute(
        select(func.count(BotInstance.id)).where(
            BotInstance.status == BotStatus.RUNNING
        )
    )
    running_bots = result.scalar()
    
    return {
        "total_users": total_users,
        "active_subscriptions": active_subs,
        "running_bots": running_bots
    }
