"""
Sol Sniper Bot PRO - Telegram API Routes
Backend endpoints for Telegram bot integration
"""
import random
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.models.models import User, Subscription, Plan, CryptoOrder, SubscriptionStatus


router = APIRouter(prefix="/telegram", tags=["Telegram"])


# ============================================================
# SCHEMAS
# ============================================================

class TelegramActivateRequest(BaseModel):
    email: str
    plan: str
    telegram_id: str
    order_id: str
    license_type: str = "desktop"  # desktop | cloud


class TelegramActivateResponse(BaseModel):
    ok: bool
    license_key: Optional[str] = None
    dashboard_url: Optional[str] = None
    error: Optional[str] = None


class TelegramStatsResponse(BaseModel):
    total_sales: float
    total_orders: int
    orders_pending: int
    orders_approved: int
    sales_by_plan: dict
    cloud_active_users: int
    licenses_created: int


class VerifyTxRequest(BaseModel):
    tx_hash: str
    expected_amount: float


class VerifyTxResponse(BaseModel):
    ok: bool
    error: Optional[str] = None


# ============================================================
# HELPERS
# ============================================================

def generate_license_key(plan_id: str) -> str:
    """Generate a license key for the given plan"""
    prefix_map = {
        "standard": "SSB-STD",
        "pro": "SSB-PRO",
        "elite": "SSB-ELITE",
        "cloud_standard": "SSB-CLD-STD",
        "cloud_pro": "SSB-CLD-PRO",
        "cloud_elite": "SSB-CLD-ELT",
    }
    prefix = prefix_map.get(plan_id.lower(), "SSB")
    part1 = random.randint(1000, 9999)
    part2 = random.randint(1000, 9999)
    return f"{prefix}-{part1}-{part2}"


async def verify_api_key(x_api_key: str = Header(None)) -> bool:
    """Verify the API key for bot requests"""
    expected_key = getattr(settings, 'TELEGRAM_API_KEY', '') or 'internal_bot_key'
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ============================================================
# ROUTES
# ============================================================

@router.post("/activate", response_model=TelegramActivateResponse)
async def activate_telegram_order(
    data: TelegramActivateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Activate a license from a Telegram order.
    Called by the Telegram bot after admin approves payment.
    """
    try:
        # Check if user exists by email
        result = await db.execute(
            select(User).where(User.email == data.email.lower())
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Create new user
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            # Generate random password (user can reset later)
            temp_password = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=12))
            
            user = User(
                email=data.email.lower(),
                password_hash=pwd_context.hash(temp_password),
                telegram_username=data.telegram_id,
            )
            db.add(user)
            await db.flush()
        
        # Update telegram_id if not set
        if not user.telegram_username:
            user.telegram_username = data.telegram_id
        
        # Map plan name to plan_id
        plan_map = {
            "STANDARD": "standard",
            "PRO": "pro",
            "ELITE": "elite",
            "CLOUD_STANDARD": "standard",
            "CLOUD_PRO": "pro",
            "CLOUD_ELITE": "elite",
        }
        plan_id = plan_map.get(data.plan.upper(), "pro")
        
        # Get plan
        plan_result = await db.execute(select(Plan).where(Plan.id == plan_id))
        plan = plan_result.scalar_one_or_none()
        
        if not plan:
            return TelegramActivateResponse(
                ok=False,
                error=f"Plan {plan_id} not found"
            )
        
        # Generate license key
        license_key = generate_license_key(data.plan)
        
        # Create subscription
        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            crypto_tx=data.order_id,
            current_period_start=datetime.utcnow(),
        )
        db.add(subscription)
        
        await db.commit()
        
        dashboard_url = f"{settings.FRONTEND_URL or 'https://your-saas.com'}/dashboard"
        
        return TelegramActivateResponse(
            ok=True,
            license_key=license_key,
            dashboard_url=dashboard_url
        )
        
    except Exception as e:
        await db.rollback()
        return TelegramActivateResponse(
            ok=False,
            error=str(e)
        )


@router.get("/stats", response_model=TelegramStatsResponse)
async def get_telegram_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get sales statistics for admin bot"""
    
    # Total sales from crypto orders
    sales_result = await db.execute(
        select(func.sum(CryptoOrder.amount_usdt))
        .where(CryptoOrder.status == "verified")
    )
    total_sales = sales_result.scalar() or 0.0
    
    # Order counts
    total_result = await db.execute(select(func.count(CryptoOrder.id)))
    total_orders = total_result.scalar() or 0
    
    pending_result = await db.execute(
        select(func.count(CryptoOrder.id))
        .where(CryptoOrder.status == "pending")
    )
    orders_pending = pending_result.scalar() or 0
    
    approved_result = await db.execute(
        select(func.count(CryptoOrder.id))
        .where(CryptoOrder.status == "verified")
    )
    orders_approved = approved_result.scalar() or 0
    
    # Sales by plan
    plan_sales_result = await db.execute(
        select(CryptoOrder.plan_id, func.sum(CryptoOrder.amount_usdt))
        .where(CryptoOrder.status == "verified")
        .group_by(CryptoOrder.plan_id)
    )
    sales_by_plan = {row[0]: row[1] for row in plan_sales_result.fetchall()}
    
    # Active cloud users (subscriptions with cloud-like plans)
    cloud_result = await db.execute(
        select(func.count(Subscription.id))
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    cloud_active = cloud_result.scalar() or 0
    
    # Total licenses (subscriptions)
    licenses_result = await db.execute(select(func.count(Subscription.id)))
    licenses_created = licenses_result.scalar() or 0
    
    return TelegramStatsResponse(
        total_sales=total_sales,
        total_orders=total_orders,
        orders_pending=orders_pending,
        orders_approved=orders_approved,
        sales_by_plan=sales_by_plan,
        cloud_active_users=cloud_active,
        licenses_created=licenses_created
    )


@router.post("/verify-tx", response_model=VerifyTxResponse)
async def verify_transaction(data: VerifyTxRequest):
    """
    Verify a USDT TRC20 transaction.
    Returns whether the TX is valid and has the expected amount.
    """
    import httpx
    
    try:
        url = "https://apilist.tronscanapi.com/api/transaction-info"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params={"hash": data.tx_hash})
            
            if resp.status_code != 200:
                return VerifyTxResponse(ok=False, error="Could not fetch TX info")
            
            tx_data = resp.json()
        
        token_info = tx_data.get("tokenTransferInfo") or {}
        amount_raw = token_info.get("amount")
        decimals = token_info.get("decimals") or 6
        
        if not amount_raw:
            return VerifyTxResponse(ok=False, error="No token transfer found")
        
        try:
            amount_usdt = float(amount_raw) / (10 ** int(decimals))
        except:
            amount_usdt = float(amount_raw)
        
        if amount_usdt >= data.expected_amount:
            return VerifyTxResponse(ok=True)
        else:
            return VerifyTxResponse(
                ok=False,
                error=f"Amount {amount_usdt} is less than expected {data.expected_amount}"
            )
            
    except Exception as e:
        return VerifyTxResponse(ok=False, error=str(e))
