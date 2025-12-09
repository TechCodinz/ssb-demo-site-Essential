"""
Sol Sniper Bot PRO - Bot Manager Service
Controls starting/stopping of bot instances per user
"""
import asyncio
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import (
    User, BotInstance, BotLog, Subscription, Plan,
    BotStatus, BotMode, LogLevel, SubscriptionStatus
)
from app.services.redis_service import redis_service


# Active bot workers (in-memory for this process)
active_workers: Dict[str, asyncio.Task] = {}


class BotManager:
    """
    Manages bot instances for users.
    Each user has one bot instance that can be started/stopped.
    """
    
    @staticmethod
    async def get_bot_state(user_id: UUID, db: AsyncSession) -> dict:
        """Get current state of user's bot"""
        result = await db.execute(
            select(BotInstance).where(BotInstance.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        
        if not bot:
            return {"status": "not_found", "running": False}
        
        return {
            "status": bot.status.value,
            "mode": bot.mode.value,
            "engine_profile": bot.engine_profile,
            "running": bot.status == BotStatus.RUNNING
        }
    
    @staticmethod
    async def can_start_live(user_id: UUID, db: AsyncSession) -> tuple[bool, str]:
        """Check if user can start LIVE mode"""
        result = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        )
        sub = result.scalar_one_or_none()
        
        if not sub:
            return False, "No active subscription. LIVE mode requires a paid plan."
        
        # Check expiry for non-lifetime
        if sub.current_period_end and sub.current_period_end < datetime.utcnow():
            return False, "Subscription expired. Please renew to use LIVE mode."
        
        return True, "OK"
    
    @staticmethod
    async def start_bot(
        user_id: UUID, 
        mode: BotMode,
        db: AsyncSession
    ) -> dict:
        """Start the user's bot instance"""
        # Get bot instance
        result = await db.execute(
            select(BotInstance).where(BotInstance.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        
        if not bot:
            return {"success": False, "error": "Bot instance not found"}
        
        if bot.status == BotStatus.RUNNING:
            return {"success": False, "error": "Bot is already running"}
        
        # Check LIVE mode permissions
        if mode == BotMode.LIVE:
            can_live, reason = await BotManager.can_start_live(user_id, db)
            if not can_live:
                return {"success": False, "error": reason}
        
        # Get subscription for engine profile
        result = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        )
        sub = result.scalar_one_or_none()
        
        if sub:
            # Get plan's engine profile
            result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
            plan = result.scalar_one_or_none()
            if plan:
                bot.engine_profile = plan.engine_profile
                bot.max_trades_per_hour = plan.max_trades_per_hour
                bot.max_open_positions = plan.max_open_positions
                bot.min_confidence_score = plan.min_confidence_score
        else:
            # DRY RUN uses ELITE for marketing
            if mode == BotMode.DRY_RUN:
                bot.engine_profile = "ELITE"
        
        # Update status
        bot.status = BotStatus.STARTING
        bot.mode = mode
        await db.commit()
        
        # Log
        await BotManager.add_log(
            bot.id, 
            f"⚡ Starting bot in {mode.value} mode with {bot.engine_profile} engine...",
            LogLevel.INFO,
            db
        )
        
        # Publish start command to worker
        await redis_service.publish_command(str(user_id), {
            "action": "start",
            "user_id": str(user_id),
            "bot_id": str(bot.id),
            "mode": mode.value,
            "engine_profile": bot.engine_profile,
            "config": {
                "rpc_url": bot.rpc_url,
                "buy_amount_sol": bot.buy_amount_sol,
                "min_liquidity_usd": bot.min_liquidity_usd,
                "min_volume_5m": bot.min_volume_5m,
                "take_profit_percent": bot.take_profit_percent,
                "stop_loss_percent": bot.stop_loss_percent,
                "max_trades_per_hour": bot.max_trades_per_hour,
                "max_open_positions": bot.max_open_positions,
                "min_confidence_score": bot.min_confidence_score,
                "session_start_hour_utc": bot.session_start_hour_utc,
                "session_end_hour_utc": bot.session_end_hour_utc,
            }
        })
        
        return {"success": True, "status": "starting", "engine_profile": bot.engine_profile}
    
    @staticmethod
    async def stop_bot(user_id: UUID, db: AsyncSession) -> dict:
        """Stop the user's bot instance"""
        result = await db.execute(
            select(BotInstance).where(BotInstance.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        
        if not bot:
            return {"success": False, "error": "Bot instance not found"}
        
        if bot.status == BotStatus.STOPPED:
            return {"success": False, "error": "Bot is not running"}
        
        # Update status
        bot.status = BotStatus.STOPPED
        await db.commit()
        
        # Log
        await BotManager.add_log(
            bot.id,
            "🛑 Bot stopped by user",
            LogLevel.INFO,
            db
        )
        
        # Publish stop command
        await redis_service.publish_command(str(user_id), {
            "action": "stop",
            "user_id": str(user_id),
            "bot_id": str(bot.id)
        })
        
        return {"success": True, "status": "stopped"}
    
    @staticmethod
    async def add_log(
        bot_id: UUID,
        message: str,
        level: LogLevel,
        db: AsyncSession,
        extra: dict = None
    ):
        """Add a log entry for a bot instance"""
        log = BotLog(
            bot_instance_id=bot_id,
            message=message,
            level=level,
            extra_json=extra
        )
        db.add(log)
        await db.commit()
        
        # Also publish to Redis for live streaming
        await redis_service.publish_log(str(bot_id), {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level.value,
            "message": message,
            "extra": extra
        })
    
    @staticmethod
    async def update_config(
        user_id: UUID,
        config: dict,
        db: AsyncSession
    ) -> dict:
        """Update bot configuration"""
        result = await db.execute(
            select(BotInstance).where(BotInstance.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        
        if not bot:
            return {"success": False, "error": "Bot instance not found"}
        
        # Update allowed fields
        allowed_fields = [
            "rpc_url", "buy_amount_sol", "min_liquidity_usd", "min_volume_5m",
            "take_profit_percent", "stop_loss_percent", "session_start_hour_utc",
            "session_end_hour_utc", "telegram_token", "telegram_chat_id"
        ]
        
        for field in allowed_fields:
            if field in config:
                setattr(bot, field, config[field])
        
        await db.commit()
        return {"success": True, "message": "Configuration updated"}


bot_manager = BotManager()
