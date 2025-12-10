"""
SSB PRO API - Authentication Router
Handles: login, signup, email verification, telegram verification
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import hashlib
import secrets
from datetime import datetime
from sqlalchemy.orm import Session

from api.config import settings
from api.services.jwt_service import create_access_token, create_refresh_token, verify_token
from api.services.email_service import send_verification_email
from api.database import get_db
from api.models.user import User

router = APIRouter()
security = HTTPBearer()
verification_tokens = {}  # Keep in memory for simple token verify or move to redis/db later

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    plan: Optional[str] = "cloud_sniper"
    ref_code: Optional[str] = None  # Referral code from URL


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class EmailVerifyRequest(BaseModel):
    token: str


class TelegramVerifyRequest(BaseModel):
    telegram_id: str
    user_id: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/signup")
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user account"""
    user = db.query(User).filter(User.email == request.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        plan=request.plan,
        verified=False,
        referred_by=request.ref_code  # Track referral!
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Generate verification token
    verify_token = secrets.token_urlsafe(32)
    verification_tokens[verify_token] = request.email
    
    # Send verification email (async)
    # await send_verification_email(request.email, verify_token)
    
    return {
        "success": True,
        "user_id": new_user.id,
        "referral_code": new_user.referral_code,  # Return their new ref code
        "verification_sent": True,
        "message": "Account created. Please verify your email."
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password"""
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if user.password_hash != hash_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate tokens
    access_token = create_access_token({"sub": user.id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "plan": user.plan,
            "verified": user.verified
        }
    )


@router.post("/email-verify")
async def verify_email(request: EmailVerifyRequest, db: Session = Depends(get_db)):
    """Verify email address with token"""
    email = verification_tokens.get(request.token)
    
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.verified = True
        db.commit()
        del verification_tokens[request.token]
        return {"success": True, "verified": True}
    
    raise HTTPException(status_code=404, detail="User not found")


@router.post("/telegram-verify")
async def link_telegram(request: TelegramVerifyRequest, db: Session = Depends(get_db)):
    """Link Telegram account to user"""
    user = db.query(User).filter(User.id == request.user_id).first()
    
    if user:
        user.telegram_id = request.telegram_id
        db.commit()
        return {"success": True, "linked": True}
    
    raise HTTPException(status_code=404, detail="User not found")


@router.post("/refresh")
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            new_access_token = create_access_token({"sub": user.id, "email": user.email})
            return {"access_token": new_access_token, "token_type": "bearer"}
        
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get current authenticated user"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user.id,
            "email": user.email,
            "plan": user.plan,
            "verified": user.verified,
            "telegram_linked": user.telegram_id is not None
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
