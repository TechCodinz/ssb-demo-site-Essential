"""
Sol Sniper Bot PRO - Auth Routes
POST /auth/register
POST /auth/login  
GET /auth/me
"""
from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, 
    create_access_token, decode_access_token
)
from app.core.config import settings
from app.models.models import User, BotInstance


router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)


# ============================================================
# SCHEMAS
# ============================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    telegram_username: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    telegram_username: Optional[str]
    created_at: str
    is_admin: bool
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ============================================================
# DEPENDENCIES
# ============================================================

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT"""
    token = None
    
    # Try Authorization header first
    if credentials:
        token = credentials.credentials
    
    # Fallback to cookie
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure user is admin"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ============================================================
# ROUTES
# ============================================================

@router.post("/register", response_model=TokenResponse)
async def register(
    data: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        telegram_username=data.telegram_username
    )
    db.add(user)
    await db.flush()
    
    # Create bot instance for user
    bot_instance = BotInstance(user_id=user.id)
    db.add(bot_instance)
    
    await db.commit()
    await db.refresh(user)
    
    # Generate token
    token = create_access_token({"sub": str(user.id)})
    
    # Set HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set True in production with HTTPS
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60
    )
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            telegram_username=user.telegram_username,
            created_at=user.created_at.isoformat(),
            is_admin=user.is_admin
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login and get access token"""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")
    
    # Generate token
    token = create_access_token({"sub": str(user.id)})
    
    # Set HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60
    )
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            telegram_username=user.telegram_username,
            created_at=user.created_at.isoformat(),
            is_admin=user.is_admin
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        telegram_username=user.telegram_username,
        created_at=user.created_at.isoformat(),
        is_admin=user.is_admin
    )


@router.post("/logout")
async def logout(response: Response):
    """Logout and clear cookie"""
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}
