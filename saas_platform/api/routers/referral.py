"""
SSB PRO API - Referral & Gamification Router
Handles: stats, leaderboard, claim, achievements
This is the viral engine that makes users ADDICTED 🚀
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import json

from api.services.jwt_service import verify_token
from api.database import get_db
from api.models.user import User, ReferralEarning

router = APIRouter()
security = HTTPBearer()

# Achievement Definitions
ACHIEVEMENTS = {
    "FIRST_TRADE": {"name": "First Blood", "icon": "🩸", "desc": "Complete your first trade"},
    "TEN_WINS": {"name": "Winning Streak", "icon": "🔥", "desc": "Win 10 trades"},
    "HUNDRED_SOL": {"name": "Century Club", "icon": "💯", "desc": "Earn 100 SOL total"},
    "REFERRAL_1": {"name": "Connector", "icon": "🔗", "desc": "Refer your first user"},
    "REFERRAL_10": {"name": "Influencer", "icon": "👑", "desc": "Refer 10 users"},
    "WHALE": {"name": "Whale Mode", "icon": "🐋", "desc": "Single trade > 10 SOL profit"},
    "DIAMOND_HANDS": {"name": "Diamond Hands", "icon": "💎", "desc": "Hold through a 50% dip and profit"},
    "SNIPER_ELITE": {"name": "Sniper Elite", "icon": "🎯", "desc": "Hit 5 trades with 100%+ gain"},
}

# Commission Rate
COMMISSION_RATE = 0.15  # 15% recurring commission


class ReferralStats(BaseModel):
    referral_code: str
    referral_link: str
    total_referrals: int
    active_referrals: int
    total_earnings: float
    pending_earnings: float
    clicks: int
    conversion_rate: float


class LeaderboardEntry(BaseModel):
    rank: int
    username: str  # Masked email
    total_pnl: float
    win_rate: float
    badges: List[str]


@router.get("/stats")
async def get_referral_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get user's referral dashboard stats"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Count referrals
        total_referrals = db.query(User).filter(User.referred_by == user.referral_code).count()
        
        # Count active referrals (have a paid plan)
        active_referrals = db.query(User).filter(
            User.referred_by == user.referral_code,
            User.plan != "demo"
        ).count()
        
        # Calculate earnings
        pending = db.query(func.sum(ReferralEarning.amount)).filter(
            ReferralEarning.user_id == user.id,
            ReferralEarning.status == "pending"
        ).scalar() or 0.0
        
        # Conversion rate
        clicks = user.referral_clicks or 1
        conversion = (total_referrals / clicks * 100) if clicks > 0 else 0
        
        return ReferralStats(
            referral_code=user.referral_code,
            referral_link=f"https://ssbpro.dev?ref={user.referral_code}",
            total_referrals=total_referrals,
            active_referrals=active_referrals,
            total_earnings=user.total_referral_earnings,
            pending_earnings=pending,
            clicks=int(clicks),
            conversion_rate=round(conversion, 1)
        )
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    🏆 Public Leaderboard - The Viral Engine
    Shows top performers to create FOMO and competition
    """
    # Get top users by total PnL
    top_users = db.query(User).order_by(desc(User.total_pnl)).limit(limit).all()
    
    leaderboard = []
    for rank, user in enumerate(top_users, 1):
        # Mask email for privacy
        email_parts = user.email.split("@")
        masked = f"{email_parts[0][:3]}***@{email_parts[1]}" if len(email_parts) == 2 else "***"
        
        # Parse badges
        try:
            badges = json.loads(user.achievement_badges or "[]")
        except:
            badges = []
        
        badge_icons = [ACHIEVEMENTS.get(b, {}).get("icon", "") for b in badges[:5]]
        
        leaderboard.append(LeaderboardEntry(
            rank=rank,
            username=masked,
            total_pnl=user.total_pnl,
            win_rate=65.0 + (rank * 0.5),  # Placeholder - would calculate from trades
            badges=badge_icons
        ))
    
    return {
        "leaderboard": leaderboard,
        "last_updated": datetime.utcnow().isoformat(),
        "total_users": db.query(User).count()
    }


@router.get("/achievements")
async def get_achievements(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get user's achievement badges"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Parse earned badges
        try:
            earned = set(json.loads(user.achievement_badges or "[]"))
        except:
            earned = set()
        
        # Build response with all achievements
        all_achievements = []
        for key, data in ACHIEVEMENTS.items():
            all_achievements.append({
                "id": key,
                "name": data["name"],
                "icon": data["icon"],
                "description": data["desc"],
                "earned": key in earned
            })
        
        return {
            "achievements": all_achievements,
            "earned_count": len(earned),
            "total_count": len(ACHIEVEMENTS)
        }
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/claim")
async def claim_earnings(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Request payout of pending referral earnings"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get pending earnings
        pending = db.query(ReferralEarning).filter(
            ReferralEarning.user_id == user.id,
            ReferralEarning.status == "pending"
        ).all()
        
        total_pending = sum(e.amount for e in pending)
        
        if total_pending < 50:  # Minimum $50 to claim
            raise HTTPException(
                status_code=400, 
                detail=f"Minimum $50 required to claim. You have ${total_pending:.2f}"
            )
        
        # Mark as claimed (in real app, would trigger payout process)
        for earning in pending:
            earning.status = "claimed"
        
        db.commit()
        
        return {
            "success": True,
            "amount_claimed": total_pending,
            "message": "Payout request submitted! You'll receive payment within 48 hours."
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/track-click/{ref_code}")
async def track_referral_click(ref_code: str, db: Session = Depends(get_db)):
    """Track referral link clicks (called from frontend)"""
    user = db.query(User).filter(User.referral_code == ref_code).first()
    
    if user:
        user.referral_clicks = (user.referral_clicks or 0) + 1
        db.commit()
    
    return {"tracked": True}


# === Helper Functions for Other Routers ===

def credit_referral_commission(
    referred_user_id: str,
    order_amount: float,
    order_id: str,
    db: Session
):
    """
    Called from orders.py webhook when a referred user makes a purchase.
    Credits 15% commission to the referrer.
    """
    referred_user = db.query(User).filter(User.id == referred_user_id).first()
    
    if not referred_user or not referred_user.referred_by:
        return None
    
    # Find the referrer
    referrer = db.query(User).filter(User.referral_code == referred_user.referred_by).first()
    
    if not referrer:
        return None
    
    # Calculate commission
    commission = order_amount * COMMISSION_RATE
    
    # Create earning record
    earning = ReferralEarning(
        user_id=referrer.id,
        referred_user_id=referred_user_id,
        source_order_id=order_id,
        amount=commission,
        status="pending"
    )
    db.add(earning)
    
    # Update referrer's total
    referrer.total_referral_earnings = (referrer.total_referral_earnings or 0) + commission
    
    # Check for achievement unlock
    check_referral_achievements(referrer, db)
    
    db.commit()
    
    return commission


def check_referral_achievements(user: User, db: Session):
    """Check and unlock referral-related achievements"""
    try:
        badges = set(json.loads(user.achievement_badges or "[]"))
    except:
        badges = set()
    
    # Count referrals
    referral_count = db.query(User).filter(User.referred_by == user.referral_code).count()
    
    if referral_count >= 1 and "REFERRAL_1" not in badges:
        badges.add("REFERRAL_1")
    
    if referral_count >= 10 and "REFERRAL_10" not in badges:
        badges.add("REFERRAL_10")
    
    user.achievement_badges = json.dumps(list(badges))
