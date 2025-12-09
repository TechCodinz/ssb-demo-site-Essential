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
from datetime import datetime, timedelta
import jwt

from api.config import settings
from api.services.jwt_service import create_access_token, create_refresh_token, verify_token
from api.services.email_service import send_verification_email

router = APIRouter()
security = HTTPBearer()

# In-memory store (replace with database in production)
users_db = {}
verification_tokens = {}


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    plan: Optional[str] = "cloud_sniper"


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
async def signup(request: SignupRequest):
    """Register a new user account"""
    if request.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = secrets.token_hex(8)
    users_db[request.email] = {
        "id": user_id,
        "email": request.email,
        "password_hash": hash_password(request.password),
        "plan": request.plan,
        "verified": False,
        "created_at": datetime.utcnow().isoformat(),
        "telegram_id": None
    }
    
    # Generate verification token
    verify_token = secrets.token_urlsafe(32)
    verification_tokens[verify_token] = request.email
    
    # Send verification email (async)
    # await send_verification_email(request.email, verify_token)
    
    return {
        "success": True,
        "user_id": user_id,
        "verification_sent": True,
        "message": "Account created. Please verify your email."
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login with email and password"""
    user = users_db.get(request.email)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if user["password_hash"] != hash_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate tokens
    access_token = create_access_token({"sub": user["id"], "email": request.email})
    refresh_token = create_refresh_token({"sub": user["id"]})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user["id"],
            "email": user["email"],
            "plan": user["plan"],
            "verified": user["verified"]
        }
    )


@router.post("/email-verify")
async def verify_email(request: EmailVerifyRequest):
    """Verify email address with token"""
    email = verification_tokens.get(request.token)
    
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    if email in users_db:
        users_db[email]["verified"] = True
        del verification_tokens[request.token]
        return {"success": True, "verified": True}
    
    raise HTTPException(status_code=404, detail="User not found")


@router.post("/telegram-verify")
async def link_telegram(request: TelegramVerifyRequest):
    """Link Telegram account to user"""
    for email, user in users_db.items():
        if user["id"] == request.user_id:
            users_db[email]["telegram_id"] = request.telegram_id
            return {"success": True, "linked": True}
    
    raise HTTPException(status_code=404, detail="User not found")


@router.post("/refresh")
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Refresh access token using refresh token"""
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        # Find user
        for email, user in users_db.items():
            if user["id"] == user_id:
                new_access_token = create_access_token({"sub": user_id, "email": email})
                return {"access_token": new_access_token, "token_type": "bearer"}
        
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        user = users_db.get(email)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user["id"],
            "email": user["email"],
            "plan": user["plan"],
            "verified": user["verified"],
            "telegram_linked": user["telegram_id"] is not None
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
