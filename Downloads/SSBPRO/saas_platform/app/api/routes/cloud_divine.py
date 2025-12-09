"""
Sol Sniper Bot PRO - Divine Features API
API endpoints for the advanced divine trading features
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.routes.cloud_auth import get_current_cloud_user
from app.models.models import CloudUser
from app.worker.divine_features import (
    ai_sentiment, cascade_detector, smart_money, gamification,
    divine_protection, auto_compound, market_regime,
    SentimentLevel, MarketRegime, ThreatLevel, AchievementType
)

router = APIRouter(prefix="/cloud/divine", tags=["Divine Features"])


# ============================================================
# SCHEMAS
# ============================================================

class SentimentResponse(BaseModel):
    fear_greed_index: int
    sentiment_level: str
    market_mood: str
    description: str


class CascadeResponse(BaseModel):
    active_cascades: int
    recent_cascade: Optional[dict]
    cascade_strength: float


class ProtectionResponse(BaseModel):
    protection_score: float
    threat_level: str
    threats_detected: List[str]
    recommendation: str


class UserProgressResponse(BaseModel):
    level: int
    xp: int
    xp_to_next: int
    rank_title: str
    total_trades: int
    win_streak: int
    best_streak: int
    total_profit_sol: float
    achievements_unlocked: int
    achievements_total: int


class AchievementResponse(BaseModel):
    name: str
    description: str
    emoji: str
    xp_reward: int
    unlocked: bool
    unlocked_at: Optional[str]


class MarketRegimeResponse(BaseModel):
    current_regime: str
    regime_emoji: str
    strategy_message: str
    confidence_modifier: int
    position_multiplier: float
    tp_multiplier: float
    sl_multiplier: float


class CompoundSettingsRequest(BaseModel):
    enabled: bool
    compound_percent: float = 50.0
    min_profit_to_compound: float = 0.1
    max_position_size: float = 2.0


# ============================================================
# SENTIMENT ENDPOINTS
# ============================================================

@router.get("/sentiment", response_model=SentimentResponse)
async def get_market_sentiment(user: CloudUser = Depends(get_current_cloud_user)):
    """Get current market Fear & Greed sentiment"""
    index = ai_sentiment.get_fear_greed_index()
    
    if index <= 20:
        level = "EXTREME_FEAR"
        mood = "😱 Extreme Fear"
        desc = "Markets are terrified. Best time to buy?"
    elif index <= 40:
        level = "FEAR"
        mood = "😨 Fear"
        desc = "Uncertainty in the market. Watch for opportunities."
    elif index <= 60:
        level = "NEUTRAL"
        mood = "😐 Neutral"
        desc = "Market is balanced. Stay alert."
    elif index <= 80:
        level = "GREED"
        mood = "🤑 Greed"
        desc = "People are getting greedy. Take profits?"
    else:
        level = "EXTREME_GREED"
        mood = "🚀 Extreme Greed"
        desc = "FOMO is extreme! Be careful of overbuying."
        
    return SentimentResponse(
        fear_greed_index=index,
        sentiment_level=level,
        market_mood=mood,
        description=desc
    )


# ============================================================
# CASCADE ENDPOINTS
# ============================================================

@router.get("/cascades", response_model=CascadeResponse)
async def get_cascade_status(user: CloudUser = Depends(get_current_cloud_user)):
    """Get momentum cascade detection status"""
    active = len(cascade_detector.active_cascades)
    
    recent = None
    if cascade_detector.cascade_history:
        last = cascade_detector.cascade_history[-1]
        recent = {
            "mint": last.mint[:12] + "...",
            "signals_aligned": last.signals_aligned,
            "strength": f"{last.cascade_strength*100:.0f}%",
            "expected_move": f"+{last.expected_move:.0f}%",
            "time": last.trigger_time.isoformat()
        }
        
    return CascadeResponse(
        active_cascades=active,
        recent_cascade=recent,
        cascade_strength=max((c.cascade_strength for c in cascade_detector.active_cascades.values()), default=0)
    )


# ============================================================
# PROTECTION ENDPOINTS
# ============================================================

@router.post("/protect/check")
async def check_token_protection(
    mint: str,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Run full protection check on a token"""
    # In production, this would fetch real contract data
    mock_data = {
        "mintAuthorityRevoked": True,
        "freezeAuthorityRevoked": True,
        "liquidityLocked": True,
        "lpBurnPercent": 60,
        "top1HolderPercent": 15,
        "devWalletPercent": 5,
        "buyTax": 0,
        "sellTax": 0
    }
    
    result = await divine_protection.full_protection_check(mint, mock_data)
    
    return ProtectionResponse(
        protection_score=result.protection_score,
        threat_level=result.threat_level.name,
        threats_detected=result.threats_detected,
        recommendation=result.recommendation
    )


@router.get("/protect/stats")
async def get_protection_stats(user: CloudUser = Depends(get_current_cloud_user)):
    """Get protection system statistics"""
    return divine_protection.protection_stats


# ============================================================
# GAMIFICATION ENDPOINTS
# ============================================================

@router.get("/progress", response_model=UserProgressResponse)
async def get_user_progress(user: CloudUser = Depends(get_current_cloud_user)):
    """Get user's gamification progress"""
    progress = gamification.get_or_create_progress(str(user.id))
    
    xp_to_next = progress.level * 100
    
    return UserProgressResponse(
        level=progress.level,
        xp=progress.xp,
        xp_to_next=xp_to_next,
        rank_title=progress.rank_title,
        total_trades=progress.total_trades,
        win_streak=progress.win_streak,
        best_streak=progress.best_streak,
        total_profit_sol=progress.total_profit_sol,
        achievements_unlocked=sum(1 for a in progress.achievements if a.unlocked),
        achievements_total=len(progress.achievements)
    )


@router.get("/achievements", response_model=List[AchievementResponse])
async def get_achievements(user: CloudUser = Depends(get_current_cloud_user)):
    """Get all achievements with unlock status"""
    progress = gamification.get_or_create_progress(str(user.id))
    
    return [
        AchievementResponse(
            name=a.name,
            description=a.description,
            emoji=a.emoji,
            xp_reward=a.xp_reward,
            unlocked=a.unlocked,
            unlocked_at=a.unlocked_at.isoformat() if a.unlocked_at else None
        )
        for a in progress.achievements
    ]


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 10,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get XP leaderboard"""
    return gamification.get_leaderboard(limit)


# ============================================================
# MARKET REGIME ENDPOINTS
# ============================================================

@router.get("/regime", response_model=MarketRegimeResponse)
async def get_market_regime(user: CloudUser = Depends(get_current_cloud_user)):
    """Get current market regime and strategy adjustments"""
    regime = market_regime.current_regime
    adjustments = market_regime.get_strategy_adjustments()
    
    emoji_map = {
        MarketRegime.BULL: "🐂",
        MarketRegime.BEAR: "🐻",
        MarketRegime.CRAB: "🦀",
        MarketRegime.VOLATILE: "🌊"
    }
    
    return MarketRegimeResponse(
        current_regime=regime.value.upper(),
        regime_emoji=emoji_map[regime],
        strategy_message=adjustments["message"],
        confidence_modifier=adjustments["confidence_modifier"],
        position_multiplier=adjustments["position_mult"],
        tp_multiplier=adjustments["tp_mult"],
        sl_multiplier=adjustments["sl_mult"]
    )


# ============================================================
# AUTO-COMPOUND ENDPOINTS
# ============================================================

@router.get("/compound/settings")
async def get_compound_settings(user: CloudUser = Depends(get_current_cloud_user)):
    """Get user's auto-compound settings"""
    settings = auto_compound.get_settings(str(user.id))
    return {
        "enabled": settings.enabled,
        "compound_percent": settings.compound_percent,
        "min_profit_to_compound": settings.min_profit_to_compound,
        "max_position_size": settings.max_position_size
    }


@router.post("/compound/settings")
async def update_compound_settings(
    settings: CompoundSettingsRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Update auto-compound settings"""
    user_settings = auto_compound.get_settings(str(user.id))
    user_settings.enabled = settings.enabled
    user_settings.compound_percent = settings.compound_percent
    user_settings.min_profit_to_compound = settings.min_profit_to_compound
    user_settings.max_position_size = settings.max_position_size
    
    return {"ok": True, "message": "Compound settings updated"}


@router.get("/compound/stats")
async def get_compound_stats(user: CloudUser = Depends(get_current_cloud_user)):
    """Get compounding statistics"""
    return auto_compound.get_compound_stats(str(user.id))


# ============================================================
# SMART MONEY ENDPOINTS
# ============================================================

@router.get("/whales")
async def get_tracked_whales(user: CloudUser = Depends(get_current_cloud_user)):
    """Get list of tracked whale wallets"""
    return [
        {
            "address": w.address[:12] + "...",
            "nickname": w.nickname,
            "win_rate": f"{w.win_rate:.1f}%",
            "avg_return": f"+{w.avg_return:.1f}%",
            "total_trades": w.total_trades,
            "following": w.following
        }
        for w in smart_money.tracked_wallets.values()
    ]


@router.get("/whales/moves")
async def get_whale_moves(
    limit: int = 20,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get recent whale moves"""
    return [
        {
            "whale": m.wallet.nickname,
            "action": m.action,
            "token": m.mint[:12] + "...",
            "amount_sol": m.amount_sol,
            "time": m.timestamp.isoformat()
        }
        for m in smart_money.recent_moves[-limit:]
    ]
