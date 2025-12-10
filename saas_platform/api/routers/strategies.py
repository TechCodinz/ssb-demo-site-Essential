"""
SSB PRO API - Strategy Sharing Router
Allows users to share their trading configurations so others can copy and profit.
This creates a viral loop where profitable users help others succeed! 🚀
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, Column, String, Float, Boolean, DateTime, Integer, Text
import json
import secrets

from api.services.jwt_service import verify_token
from api.database import get_db, Base
from api.models.user import User

router = APIRouter()
security = HTTPBearer()


# ==================== DATABASE MODEL ====================

class SharedStrategy(Base):
    """User-shared trading strategies/configs"""
    __tablename__ = "shared_strategies"
    
    id = Column(String, primary_key=True, default=lambda: secrets.token_hex(8))
    user_id = Column(String, index=True)
    name = Column(String)
    description = Column(Text)
    
    # Trading config
    risk_level = Column(String, default="medium")  # low, medium, high, degen
    min_confidence = Column(Float, default=75)
    max_position_size = Column(Float, default=0.5)
    take_profit = Column(Float, default=30)
    stop_loss = Column(Float, default=15)
    trailing_stop = Column(Boolean, default=True)
    
    # Performance metrics
    total_pnl = Column(Float, default=0)
    win_rate = Column(Float, default=0)
    total_trades = Column(Integer, default=0)
    best_trade = Column(Float, default=0)
    
    # Social metrics
    upvotes = Column(Integer, default=0)
    downloads = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ==================== REQUEST/RESPONSE MODELS ====================

class StrategyShareRequest(BaseModel):
    name: str
    description: str
    risk_level: str = "medium"
    min_confidence: float = 75
    max_position_size: float = 0.5
    take_profit: float = 30
    stop_loss: float = 15
    trailing_stop: bool = True


class StrategyResponse(BaseModel):
    id: str
    name: str
    description: str
    author: str
    risk_level: str
    min_confidence: float
    max_position_size: float
    take_profit: float
    stop_loss: float
    trailing_stop: bool
    total_pnl: float
    win_rate: float
    total_trades: int
    upvotes: int
    downloads: int
    is_featured: bool


# ==================== ENDPOINTS ====================

@router.get("/browse")
async def browse_strategies(
    sort_by: str = "pnl",  # pnl, upvotes, downloads, new
    risk_level: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    🔥 Browse community-shared trading strategies
    Find the config that makes others profitable!
    """
    query = db.query(SharedStrategy)
    
    if risk_level:
        query = query.filter(SharedStrategy.risk_level == risk_level)
    
    # Sort
    if sort_by == "pnl":
        query = query.order_by(desc(SharedStrategy.total_pnl))
    elif sort_by == "upvotes":
        query = query.order_by(desc(SharedStrategy.upvotes))
    elif sort_by == "downloads":
        query = query.order_by(desc(SharedStrategy.downloads))
    else:
        query = query.order_by(desc(SharedStrategy.created_at))
    
    strategies = query.limit(limit).all()
    
    results = []
    for strat in strategies:
        # Get author info
        author = db.query(User).filter(User.id == strat.user_id).first()
        author_name = "Anonymous"
        if author:
            email_parts = author.email.split("@")
            author_name = f"{email_parts[0][:3]}***" if email_parts else "***"
        
        results.append(StrategyResponse(
            id=strat.id,
            name=strat.name,
            description=strat.description,
            author=author_name,
            risk_level=strat.risk_level,
            min_confidence=strat.min_confidence,
            max_position_size=strat.max_position_size,
            take_profit=strat.take_profit,
            stop_loss=strat.stop_loss,
            trailing_stop=strat.trailing_stop,
            total_pnl=strat.total_pnl,
            win_rate=strat.win_rate,
            total_trades=strat.total_trades,
            upvotes=strat.upvotes,
            downloads=strat.downloads,
            is_featured=strat.is_featured
        ))
    
    return {
        "strategies": results,
        "total": len(results)
    }


@router.post("/share")
async def share_strategy(
    request: StrategyShareRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    📤 Share your profitable strategy with the community
    Help others succeed and build your reputation!
    """
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create the strategy
        strategy = SharedStrategy(
            user_id=user.id,
            name=request.name,
            description=request.description,
            risk_level=request.risk_level,
            min_confidence=request.min_confidence,
            max_position_size=request.max_position_size,
            take_profit=request.take_profit,
            stop_loss=request.stop_loss,
            trailing_stop=request.trailing_stop,
            # Performance will be updated from user's actual results
            total_pnl=user.total_pnl or 0,
            win_rate=65.0,  # Would calculate from actual trades
            total_trades=100
        )
        
        db.add(strategy)
        db.commit()
        
        return {
            "success": True,
            "strategy_id": strategy.id,
            "message": "Strategy shared with the community! 🚀"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_id}/apply")
async def apply_strategy(
    strategy_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    ⬇️ Apply a community strategy to your bot
    One-click to use a profitable config!
    """
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        strategy = db.query(SharedStrategy).filter(SharedStrategy.id == strategy_id).first()
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        # Increment download count
        strategy.downloads += 1
        db.commit()
        
        # Return the config for the frontend to apply
        return {
            "success": True,
            "config": {
                "min_confidence": strategy.min_confidence,
                "max_position_size": strategy.max_position_size,
                "take_profit": strategy.take_profit,
                "stop_loss": strategy.stop_loss,
                "trailing_stop": strategy.trailing_stop,
                "risk_level": strategy.risk_level
            },
            "message": f"Applied '{strategy.name}' config! Good luck! 🍀"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_id}/upvote")
async def upvote_strategy(
    strategy_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """👍 Upvote a strategy that helped you profit"""
    try:
        payload = verify_token(credentials.credentials)
        
        strategy = db.query(SharedStrategy).filter(SharedStrategy.id == strategy_id).first()
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        strategy.upvotes += 1
        db.commit()
        
        return {
            "success": True,
            "upvotes": strategy.upvotes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-strategies")
async def get_my_strategies(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get strategies you've shared"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        strategies = db.query(SharedStrategy).filter(SharedStrategy.user_id == user.id).all()
        
        return {
            "strategies": [{
                "id": s.id,
                "name": s.name,
                "upvotes": s.upvotes,
                "downloads": s.downloads,
                "pnl": s.total_pnl
            } for s in strategies],
            "total": len(strategies)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profit-tracker")
async def get_profit_tracker(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    📊 Track if user is making enough to cover subscription
    Shows: earnings vs subscription cost
    """
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Subscription costs
        PLAN_COSTS = {
            "standard": 49,
            "cloud_sniper": 99,
            "pro": 149,
            "elite": 249
        }
        
        subscription_cost = PLAN_COSTS.get(user.plan, 99)
        monthly_pnl = user.total_pnl or 0  # Would calculate from this month's trades
        referral_earnings = user.total_referral_earnings or 0
        
        total_income = monthly_pnl + referral_earnings
        covers_subscription = total_income >= subscription_cost
        
        return {
            "subscription_cost": subscription_cost,
            "trading_pnl": monthly_pnl,
            "referral_earnings": referral_earnings,
            "total_income": total_income,
            "covers_subscription": covers_subscription,
            "surplus": max(0, total_income - subscription_cost),
            "message": "🎉 You're in profit!" if covers_subscription else f"${subscription_cost - total_income:.0f} more to cover subscription"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
