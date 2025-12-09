"""
SSB PRO API - User Router
Handles: cloud status, profile, usage stats
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from api.services.jwt_service import verify_token
from api.database import get_db
from api.models.user import User
from api.models.license import License

router = APIRouter()
security = HTTPBearer()

# Mock cloud sessions (replace with actual tracking in Redis later)
cloud_sessions = {}


@router.get("/cloud-status")
async def get_cloud_status(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get current cloud bot status for user"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        
        # Find user's license and session
        session = cloud_sessions.get(email, {})
        
        # Find license
        license_data = db.query(License).filter(License.email == email).first()
        
        if not license_data:
            return {
                "active": False,
                "message": "No active license"
            }
        
        return {
            "active": session.get("active", False),
            "plan": license_data.plan,
            "bot_status": session.get("bot_status", "stopped"),
            "trades_today": session.get("trades_today", 0),
            "open_positions": session.get("open_positions", 0),
            "pnl_today": session.get("pnl_today", 0.0),
            "uptime": session.get("uptime", "0h 0m"),
            "last_trade": session.get("last_trade"),
            "rpc_status": "connected",
            "validation_status": "valid"
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/profile")
async def get_profile(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get user profile"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Find license
        license_data = db.query(License).filter(License.email == email).first()
        
        license_info = None
        if license_data:
            license_info = {
                "plan": license_data.plan,
                "expires": license_data.expires.isoformat(),
                "activated": license_data.activated
            }
        
        return {
            "id": user.id,
            "email": user.email,
            "verified": user.verified,
            "telegram_linked": user.telegram_id is not None,
            "created_at": user.created_at.isoformat(),
            "license": license_info
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/usage")
async def get_usage(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get usage statistics"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        
        session = cloud_sessions.get(email, {})
        
        return {
            "trades_today": session.get("trades_today", 0),
            "trades_this_month": session.get("trades_month", 0),
            "total_volume": session.get("total_volume", 0.0),
            "pnl_today": session.get("pnl_today", 0.0),
            "pnl_this_month": session.get("pnl_month", 0.0),
            "tokens_scanned": session.get("tokens_scanned", 0),
            "signals_detected": session.get("signals_detected", 0),
            "rugs_avoided": session.get("rugs_avoided", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/billing")
async def get_billing(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get billing information"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        
        # Find license
        license_data = db.query(License).filter(License.email == email).first()
        
        if license_data:
            days_left = (license_data.expires - datetime.utcnow()).days
            
            return {
                "plan": license_data.plan,
                "renewal_date": license_data.expires.isoformat(),
                "days_until_renewal": max(0, days_left),
                "auto_renew": False,
                "payment_method": "USDT TRC20"
            }
        
        return {"has_subscription": False}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
