"""
Sol Sniper Bot PRO - Billing Routes
USDT TRC20 Crypto Payments
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.core.security import generate_reference_code
from app.models.models import (
    User, Plan, Subscription, CryptoOrder,
    SubscriptionStatus, BillingType
)
from app.api.routes.auth import get_current_user


router = APIRouter(prefix="/billing", tags=["Billing"])


# ============================================================
# SCHEMAS
# ============================================================

class CreateOrderRequest(BaseModel):
    plan_id: str  # standard, pro, elite


class OrderResponse(BaseModel):
    order_id: str
    reference_code: str
    amount_usdt: float
    wallet_address: str
    plan_id: str
    plan_name: str
    status: str


class VerifyTxRequest(BaseModel):
    reference_code: str
    tx_hash: str


class SubscriptionResponse(BaseModel):
    id: str
    plan_id: str
    plan_name: str
    status: str
    billing_type: str
    created_at: str
    expires_at: Optional[str]


# ============================================================
# ROUTES
# ============================================================

@router.get("/plans")
async def get_plans(db: AsyncSession = Depends(get_db)):
    """Get all available plans"""
    result = await db.execute(select(Plan))
    plans = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "lifetime_price": p.lifetime_price,
            "engine_profile": p.engine_profile,
            "max_trades_per_hour": p.max_trades_per_hour,
            "max_open_positions": p.max_open_positions,
            "notes": p.notes
        }
        for p in plans
    ]


@router.post("/create-crypto-order", response_model=OrderResponse)
async def create_crypto_order(
    data: CreateOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new crypto payment order"""
    # Get plan
    result = await db.execute(select(Plan).where(Plan.id == data.plan_id))
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check if user already has active subscription for this plan or higher
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing and existing.plan_id == data.plan_id:
        raise HTTPException(status_code=400, detail="You already have this plan active")
    
    # Create order
    order = CryptoOrder(
        user_id=user.id,
        plan_id=plan.id,
        amount_usdt=plan.lifetime_price,
        reference_code=generate_reference_code()
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    
    return OrderResponse(
        order_id=str(order.id),
        reference_code=order.reference_code,
        amount_usdt=order.amount_usdt,
        wallet_address=settings.USDT_WALLET_ADDRESS,
        plan_id=plan.id,
        plan_name=plan.name,
        status=order.status
    )


@router.post("/verify-crypto-tx")
async def verify_crypto_tx(
    data: VerifyTxRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify a crypto transaction and activate subscription"""
    # Find order
    result = await db.execute(
        select(CryptoOrder).where(
            CryptoOrder.reference_code == data.reference_code,
            CryptoOrder.user_id == user.id
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status == "verified":
        raise HTTPException(status_code=400, detail="Order already verified")
    
    # Verify on TronScan
    verified = await verify_tron_transaction(
        tx_hash=data.tx_hash,
        expected_amount=order.amount_usdt,
        expected_wallet=settings.USDT_WALLET_ADDRESS
    )
    
    if not verified:
        raise HTTPException(
            status_code=400, 
            detail="Transaction not verified. Please check TX hash and ensure payment is complete."
        )
    
    # Update order
    order.tx_hash = data.tx_hash
    order.status = "verified"
    order.verified_at = datetime.utcnow()
    
    # Get plan
    result = await db.execute(select(Plan).where(Plan.id == order.plan_id))
    plan = result.scalar_one_or_none()
    
    # Create subscription
    subscription = Subscription(
        user_id=user.id,
        plan_id=order.plan_id,
        billing_type=BillingType.LIFETIME,
        status=SubscriptionStatus.ACTIVE,
        crypto_tx=data.tx_hash,
        current_period_start=datetime.utcnow(),
        current_period_end=None  # Lifetime
    )
    db.add(subscription)
    
    # Update bot instance with plan limits
    if user.bot_instance:
        user.bot_instance.engine_profile = plan.engine_profile
        user.bot_instance.max_trades_per_hour = plan.max_trades_per_hour
        user.bot_instance.max_open_positions = plan.max_open_positions
        user.bot_instance.min_confidence_score = plan.min_confidence_score
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Payment verified! {plan.name} plan activated.",
        "plan": plan.name,
        "engine_profile": plan.engine_profile
    }


@router.get("/subscription", response_model=Optional[SubscriptionResponse])
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's active subscription"""
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).order_by(Subscription.created_at.desc())
    )
    sub = result.scalar_one_or_none()
    
    if not sub:
        return None
    
    # Get plan name
    result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
    plan = result.scalar_one_or_none()
    
    return SubscriptionResponse(
        id=str(sub.id),
        plan_id=sub.plan_id,
        plan_name=plan.name if plan else sub.plan_id,
        status=sub.status.value,
        billing_type=sub.billing_type.value,
        created_at=sub.created_at.isoformat(),
        expires_at=sub.current_period_end.isoformat() if sub.current_period_end else None
    )


@router.get("/orders")
async def get_orders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's payment orders"""
    result = await db.execute(
        select(CryptoOrder).where(CryptoOrder.user_id == user.id).order_by(CryptoOrder.created_at.desc())
    )
    orders = result.scalars().all()
    
    return [
        {
            "id": str(o.id),
            "reference_code": o.reference_code,
            "plan_id": o.plan_id,
            "amount_usdt": o.amount_usdt,
            "status": o.status,
            "created_at": o.created_at.isoformat(),
            "tx_hash": o.tx_hash
        }
        for o in orders
    ]


# ============================================================
# TRON VERIFICATION
# ============================================================

async def verify_tron_transaction(
    tx_hash: str,
    expected_amount: float,
    expected_wallet: str
) -> bool:
    """Verify USDT TRC20 transaction on TronScan"""
    try:
        url = f"https://apilist.tronscan.org/api/transaction-info?hash={tx_hash}"
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            
            if resp.status_code != 200:
                return False
            
            data = resp.json()
            
            # Check if it's a TRC20 transfer
            if not data.get("contractData"):
                return False
            
            contract_data = data.get("contractData", {})
            to_address = contract_data.get("to_address", "")
            
            # Get token info
            token_info = data.get("tokenTransferInfo", {})
            if not token_info:
                # Try trc20TransferInfo
                trc20_info = data.get("trc20TransferInfo", [])
                if trc20_info:
                    token_info = trc20_info[0]
            
            # Verify recipient
            if to_address.lower() != expected_wallet.lower():
                return False
            
            # Verify amount (USDT has 6 decimals)
            amount_str = token_info.get("amount_str", "0")
            decimals = int(token_info.get("decimals", 6))
            amount = float(amount_str) / (10 ** decimals)
            
            # Allow 1% tolerance for fees
            if amount < expected_amount * 0.99:
                return False
            
            # Verify confirmed
            if not data.get("confirmed", False):
                return False
            
            return True
            
    except Exception as e:
        print(f"TronScan verification error: {e}")
        return False
