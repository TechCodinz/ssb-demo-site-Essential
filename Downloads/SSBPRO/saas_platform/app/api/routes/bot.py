"""
Sol Sniper Bot PRO - Bot Routes
Start/Stop bot, get status, update config
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import json

from app.core.database import get_db
from app.models.models import User, BotInstance, BotLog, BotMode, BotStatus
from app.api.routes.auth import get_current_user
from app.services.bot_manager import bot_manager
from app.services.redis_service import redis_service


router = APIRouter(prefix="/bot", tags=["Bot Management"])


# ============================================================
# SCHEMAS
# ============================================================

class StartBotRequest(BaseModel):
    mode: str = "DRY_RUN"  # DRY_RUN or LIVE


class UpdateConfigRequest(BaseModel):
    rpc_url: Optional[str] = None
    buy_amount_sol: Optional[float] = None
    min_liquidity_usd: Optional[float] = None
    min_volume_5m: Optional[float] = None
    take_profit_percent: Optional[float] = None
    stop_loss_percent: Optional[float] = None
    session_start_hour_utc: Optional[int] = None
    session_end_hour_utc: Optional[int] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


# ============================================================
# ROUTES
# ============================================================

@router.get("/status")
async def get_bot_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current bot status"""
    state = await bot_manager.get_bot_state(user.id, db)
    
    # Get bot config
    result = await db.execute(
        select(BotInstance).where(BotInstance.user_id == user.id)
    )
    bot = result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(status_code=404, detail="Bot instance not found")
    
    return {
        **state,
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
    }


@router.post("/start")
async def start_bot(
    data: StartBotRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start the bot"""
    try:
        mode = BotMode(data.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mode. Use DRY_RUN or LIVE")
    
    result = await bot_manager.start_bot(user.id, mode, db)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/stop")
async def stop_bot(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Stop the bot"""
    result = await bot_manager.stop_bot(user.id, db)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/config")
async def update_bot_config(
    data: UpdateConfigRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update bot configuration"""
    config = data.model_dump(exclude_unset=True)
    result = await bot_manager.update_config(user.id, config, db)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/logs")
async def get_bot_logs(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recent bot logs"""
    result = await db.execute(
        select(BotInstance).where(BotInstance.user_id == user.id)
    )
    bot = result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(status_code=404, detail="Bot instance not found")
    
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
            "message": log.message,
            "extra": log.extra_json
        }
        for log in reversed(logs)
    ]


# ============================================================
# WEBSOCKET FOR LIVE LOGS
# ============================================================

@router.websocket("/ws/logs")
async def websocket_logs(
    websocket: WebSocket,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """WebSocket for live log streaming"""
    await websocket.accept()
    
    # Authenticate via query param
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return
    
    from app.core.security import decode_access_token
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    # Get bot instance
    result = await db.execute(
        select(BotInstance).where(BotInstance.user_id == UUID(user_id))
    )
    bot = result.scalar_one_or_none()
    
    if not bot:
        await websocket.close(code=4004, reason="Bot not found")
        return
    
    # Send initial logs
    result = await db.execute(
        select(BotLog)
        .where(BotLog.bot_instance_id == bot.id)
        .order_by(BotLog.timestamp.desc())
        .limit(50)
    )
    logs = result.scalars().all()
    
    for log in reversed(logs):
        await websocket.send_json({
            "type": "log",
            "data": {
                "timestamp": log.timestamp.isoformat(),
                "level": log.level.value,
                "message": log.message
            }
        })
    
    # Subscribe to Redis for live updates
    try:
        async def on_log(data):
            await websocket.send_json({"type": "log", "data": data})
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
    except Exception:
        pass
