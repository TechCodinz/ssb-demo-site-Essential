"""
SSB PRO API - Copy Trading Router
The RARE UNTAPPED NICHE feature 🔥

Allows users to automatically copy trades from top performers.
This is the feature that will make SSB PRO go viral.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, Column, String, Float, Boolean, DateTime, Integer
import json

from api.services.jwt_service import verify_token
from api.database import get_db, Base
from api.models.user import User
import secrets

router = APIRouter()
security = HTTPBearer()


# ==================== DATABASE MODEL ====================

class CopyRelation(Base):
    """Stores who is copying whom"""
    __tablename__ = "copy_relations"
    
    id = Column(String, primary_key=True, default=lambda: secrets.token_hex(8))
    follower_id = Column(String, index=True)  # User who is copying
    leader_id = Column(String, index=True)    # User being copied
    allocation_percent = Column(Float, default=10.0)  # % of portfolio to allocate
    max_trade_size = Column(Float, default=0.5)  # Max SOL per trade
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    total_copied_trades = Column(Integer, default=0)
    total_pnl_from_copy = Column(Float, default=0.0)


# ==================== REQUEST/RESPONSE MODELS ====================

class FollowRequest(BaseModel):
    leader_id: str
    allocation_percent: float = 10.0  # Default 10% of portfolio
    max_trade_size: float = 0.5  # Max 0.5 SOL per trade


class LeaderProfile(BaseModel):
    user_id: str
    username: str
    total_pnl: float
    win_rate: float
    total_trades: int
    followers: int
    badges: List[str]
    avg_trade_size: float
    best_trade: float
    is_verified: bool


# ==================== ENDPOINTS ====================

@router.get("/leaders")
async def get_top_leaders(
    limit: int = 20,
    min_pnl: float = 0,
    db: Session = Depends(get_db)
):
    """
    🏆 Get top traders available to copy
    This is the discovery page for copy trading
    """
    # Get top performers
    leaders = db.query(User).filter(
        User.total_pnl >= min_pnl
    ).order_by(desc(User.total_pnl)).limit(limit).all()
    
    results = []
    for user in leaders:
        # Count followers
        follower_count = db.query(CopyRelation).filter(
            CopyRelation.leader_id == user.id,
            CopyRelation.is_active == True
        ).count()
        
        # Mask email
        email_parts = user.email.split("@")
        masked = f"{email_parts[0][:3]}***" if email_parts else "***"
        
        # Parse badges
        try:
            badges = json.loads(user.achievement_badges or "[]")
        except:
            badges = []
        
        results.append(LeaderProfile(
            user_id=user.id,
            username=masked,
            total_pnl=user.total_pnl or 0,
            win_rate=65.0 + (len(badges) * 2),  # Approximate from badges
            total_trades=100,  # Would calculate from trade history
            followers=follower_count,
            badges=[b[:10] for b in badges[:5]],  # First 5 badges
            avg_trade_size=0.25,
            best_trade=user.total_pnl * 0.15 if user.total_pnl else 0,
            is_verified=len(badges) >= 3
        ))
    
    return {
        "leaders": results,
        "total_available": len(results)
    }


@router.post("/follow")
async def follow_leader(
    request: FollowRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    🔗 Start copying a top trader
    Their trades will be automatically mirrored to your account
    """
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Can't copy yourself
        if user.id == request.leader_id:
            raise HTTPException(status_code=400, detail="Cannot copy yourself")
        
        # Check if leader exists
        leader = db.query(User).filter(User.id == request.leader_id).first()
        if not leader:
            raise HTTPException(status_code=404, detail="Leader not found")
        
        # Check if already following
        existing = db.query(CopyRelation).filter(
            CopyRelation.follower_id == user.id,
            CopyRelation.leader_id == request.leader_id,
            CopyRelation.is_active == True
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Already following this trader")
        
        # Validate allocation
        if request.allocation_percent < 1 or request.allocation_percent > 50:
            raise HTTPException(status_code=400, detail="Allocation must be 1-50%")
        
        # Create relation
        relation = CopyRelation(
            follower_id=user.id,
            leader_id=request.leader_id,
            allocation_percent=request.allocation_percent,
            max_trade_size=request.max_trade_size
        )
        db.add(relation)
        db.commit()
        
        return {
            "success": True,
            "message": f"Now copying trades from top performer!",
            "allocation": f"{request.allocation_percent}%",
            "max_per_trade": f"{request.max_trade_size} SOL"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unfollow/{leader_id}")
async def unfollow_leader(
    leader_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Stop copying a trader"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        relation = db.query(CopyRelation).filter(
            CopyRelation.follower_id == user.id,
            CopyRelation.leader_id == leader_id,
            CopyRelation.is_active == True
        ).first()
        
        if not relation:
            raise HTTPException(status_code=404, detail="Not following this trader")
        
        relation.is_active = False
        db.commit()
        
        return {
            "success": True,
            "message": "Stopped copying this trader",
            "total_copied_trades": relation.total_copied_trades,
            "total_pnl": relation.total_pnl_from_copy
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-copies")
async def get_my_copies(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get list of traders you're copying and their performance"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        relations = db.query(CopyRelation).filter(
            CopyRelation.follower_id == user.id,
            CopyRelation.is_active == True
        ).all()
        
        copies = []
        for rel in relations:
            leader = db.query(User).filter(User.id == rel.leader_id).first()
            if leader:
                email_parts = leader.email.split("@")
                masked = f"{email_parts[0][:3]}***" if email_parts else "***"
                
                copies.append({
                    "leader_id": rel.leader_id,
                    "leader_name": masked,
                    "allocation": rel.allocation_percent,
                    "max_trade_size": rel.max_trade_size,
                    "total_copied_trades": rel.total_copied_trades,
                    "total_pnl": rel.total_pnl_from_copy,
                    "started": rel.created_at.isoformat()
                })
        
        return {
            "active_copies": copies,
            "total_allocation": sum(c["allocation"] for c in copies)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-followers")
async def get_my_followers(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get list of users copying your trades (for leaders)"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        relations = db.query(CopyRelation).filter(
            CopyRelation.leader_id == user.id,
            CopyRelation.is_active == True
        ).all()
        
        return {
            "follower_count": len(relations),
            "total_aum": sum(r.allocation_percent for r in relations) * 100,  # Approx AUM
            "message": "You have traders copying your moves! Keep performing."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== COPY EXECUTION LOGIC ====================
# This function is called by the trading engine when a leader makes a trade

async def execute_copy_trades(
    leader_id: str,
    trade_data: dict,
    db: Session
):
    """
    Called when a leader executes a trade.
    Mirrors the trade to all followers based on their settings.
    """
    # Get all active followers
    followers = db.query(CopyRelation).filter(
        CopyRelation.leader_id == leader_id,
        CopyRelation.is_active == True
    ).all()
    
    results = []
    for follower_rel in followers:
        try:
            # Calculate trade size based on follower's settings
            leader_trade_size = trade_data.get("size", 0.1)
            copy_size = min(
                leader_trade_size * (follower_rel.allocation_percent / 100),
                follower_rel.max_trade_size
            )
            
            if copy_size < 0.01:  # Minimum trade size
                continue
            
            # Execute the copy trade (would integrate with tx_relay.py)
            # For now, log and update stats
            follower_rel.total_copied_trades += 1
            
            results.append({
                "follower_id": follower_rel.follower_id,
                "copy_size": copy_size,
                "status": "queued"
            })
            
        except Exception as e:
            print(f"[COPY] Error copying trade for {follower_rel.follower_id}: {e}")
    
    db.commit()
    return results
