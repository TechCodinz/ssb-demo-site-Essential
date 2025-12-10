"""
Sol Sniper Bot PRO - Infrastructure API Routes
API endpoints for RPC, payments, and transaction relay services.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.api.routes.cloud_auth import get_current_cloud_user
from app.models.models import CloudUser
from app.services.rpc_manager import rpc_manager, RPCTier
from app.services.usdt_payments import payment_service, PLAN_PRICES
from app.services.tx_relay import tx_relay
from app.services.infrastructure import dexscreener, honeypot_api, jupiter

router = APIRouter(prefix="/cloud/infra", tags=["Infrastructure"])


# ============================================================
# SCHEMAS
# ============================================================

class RPCStatsResponse(BaseModel):
    tier: str
    total_endpoints: int
    healthy_endpoints: int
    endpoints: List[dict]


class PaymentAddressRequest(BaseModel):
    plan: str


class PaymentAddressResponse(BaseModel):
    address: str
    amount: float
    plan: str
    expires_at: str
    payment_id: str


class PaymentVerifyRequest(BaseModel):
    tx_hash: str
    plan: str


class PaymentVerifyResponse(BaseModel):
    success: bool
    message: str


class SubscriptionResponse(BaseModel):
    active: bool
    plan: Optional[str]
    status: str
    days_remaining: int
    end_date: Optional[str]
    auto_renew: bool


class TransactionSubmitRequest(BaseModel):
    signed_tx: str
    tx_type: str = "SWAP"
    token_mint: str = ""
    amount_sol: float = 0.0


class TransactionResponse(BaseModel):
    success: bool
    signature: Optional[str]
    error: Optional[str]


class SwapQuoteRequest(BaseModel):
    input_mint: str
    output_mint: str
    amount: int
    slippage_bps: int = 100


class SwapTransactionRequest(BaseModel):
    input_mint: str
    output_mint: str
    amount: int
    user_pubkey: str
    slippage_bps: int = 100


class TokenCheckRequest(BaseModel):
    address: str


# ============================================================
# RPC ENDPOINTS (ADMIN ONLY)
# ============================================================

@router.get("/rpc/stats", response_model=RPCStatsResponse)
async def get_rpc_stats(user: CloudUser = Depends(get_current_cloud_user)):
    """Get RPC health and usage statistics (available to all users)"""
    stats = rpc_manager.get_stats()
    
    # Hide sensitive info for non-admins
    for endpoint in stats["endpoints"]:
        endpoint.pop("url", None)
        endpoint.pop("last_error", None)
    
    return RPCStatsResponse(
        tier=stats["tier"],
        total_endpoints=stats["total_endpoints"],
        healthy_endpoints=stats["healthy_endpoints"],
        endpoints=stats["endpoints"]
    )


@router.get("/rpc/status")
async def get_rpc_status(user: CloudUser = Depends(get_current_cloud_user)):
    """Get simplified RPC status for dashboard"""
    stats = rpc_manager.get_stats()
    
    # Determine overall status
    healthy = stats["healthy_endpoints"]
    total = stats["total_endpoints"]
    
    if healthy == total:
        status_label = "Optimal"
        status_color = "green"
    elif healthy > 0:
        status_label = "Degraded"
        status_color = "yellow"
    else:
        status_label = "Down"
        status_color = "red"
    
    # Get current provider
    current_provider = "Unknown"
    for ep in stats["endpoints"]:
        if ep["status"] == "healthy" and ep["is_primary"]:
            current_provider = ep["name"]
            break
    
    # Get average latency
    avg_latency = sum(ep["latency_ms"] for ep in stats["endpoints"]) / max(len(stats["endpoints"]), 1)
    
    latency_label = "Fast"
    if avg_latency > 200:
        latency_label = "Slow"
    elif avg_latency > 100:
        latency_label = "Moderate"
    
    return {
        "status": status_label,
        "status_color": status_color,
        "tier": stats["tier"],
        "provider": current_provider,
        "latency_ms": round(avg_latency, 2),
        "latency_label": latency_label,
        "healthy_count": healthy,
        "total_count": total
    }


# ============================================================
# PAYMENT ENDPOINTS
# ============================================================

@router.post("/payments/create", response_model=PaymentAddressResponse)
async def create_payment_address(
    request: PaymentAddressRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Generate a payment address for subscription"""
    if request.plan not in PLAN_PRICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan. Choose from: {list(PLAN_PRICES.keys())}"
        )
    
    payment = payment_service.generate_payment_address(
        user_id=str(user.id),
        plan=request.plan
    )
    
    return PaymentAddressResponse(
        address=payment.address,
        amount=payment.expected_amount,
        plan=payment.plan,
        expires_at=payment.expires_at.isoformat(),
        payment_id=payment.id
    )


@router.post("/payments/verify", response_model=PaymentVerifyResponse)
async def verify_payment(
    request: PaymentVerifyRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Verify a USDT payment transaction"""
    if request.plan not in PLAN_PRICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan"
        )
    
    success, message = await payment_service.verify_payment(
        tx_hash=request.tx_hash,
        expected_amount=PLAN_PRICES[request.plan],
        user_id=str(user.id),
        plan=request.plan
    )
    
    return PaymentVerifyResponse(success=success, message=message)


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription_status(user: CloudUser = Depends(get_current_cloud_user)):
    """Get subscription status for current user"""
    status_data = await payment_service.check_subscription_status(str(user.id))
    
    return SubscriptionResponse(
        active=status_data["active"],
        plan=status_data.get("plan"),
        status=status_data["status"],
        days_remaining=status_data["days_remaining"],
        end_date=status_data.get("end_date"),
        auto_renew=status_data.get("auto_renew", False)
    )


@router.get("/payments/history")
async def get_payment_history(user: CloudUser = Depends(get_current_cloud_user)):
    """Get payment history for current user"""
    return payment_service.get_payment_history(str(user.id))


@router.post("/subscription/cancel")
async def cancel_subscription(user: CloudUser = Depends(get_current_cloud_user)):
    """Cancel auto-renewal for subscription"""
    await payment_service.cancel_subscription(str(user.id))
    return {"ok": True, "message": "Auto-renewal cancelled"}


# ============================================================
# TRANSACTION ENDPOINTS
# ============================================================

@router.post("/tx/submit", response_model=TransactionResponse)
async def submit_transaction(
    request: TransactionSubmitRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Submit a signed transaction for broadcast"""
    result = await tx_relay.submit_transaction(
        user_id=str(user.id),
        plan=user.plan,
        signed_tx_base64=request.signed_tx,
        tx_type=request.tx_type,
        token_mint=request.token_mint,
        amount_sol=request.amount_sol
    )
    
    return TransactionResponse(
        success=result.success,
        signature=result.signature,
        error=result.error
    )


@router.post("/tx/submit-confirm", response_model=TransactionResponse)
async def submit_and_confirm_transaction(
    request: TransactionSubmitRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Submit a transaction and wait for confirmation"""
    result = await tx_relay.submit_and_confirm(
        user_id=str(user.id),
        plan=user.plan,
        signed_tx_base64=request.signed_tx,
        tx_type=request.tx_type,
        token_mint=request.token_mint,
        amount_sol=request.amount_sol,
        timeout=30
    )
    
    return TransactionResponse(
        success=result.success,
        signature=result.signature,
        error=result.error
    )


@router.get("/tx/history")
async def get_transaction_history(
    limit: int = 50,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get transaction history for current user"""
    return tx_relay.get_user_transactions(str(user.id), limit=limit)


@router.get("/tx/stats")
async def get_transaction_stats(user: CloudUser = Depends(get_current_cloud_user)):
    """Get transaction statistics for current user"""
    return tx_relay.get_user_stats(str(user.id))


# ============================================================
# JUPITER SWAP ENDPOINTS
# ============================================================

@router.post("/jupiter/quote")
async def get_jupiter_quote(
    request: SwapQuoteRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get a swap quote from Jupiter"""
    quote = await jupiter.get_quote(
        input_mint=request.input_mint,
        output_mint=request.output_mint,
        amount=request.amount,
        slippage_bps=request.slippage_bps
    )
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get swap quote"
        )
    
    return {
        "input_mint": quote.input_mint,
        "output_mint": quote.output_mint,
        "amount_in": quote.amount_in,
        "amount_out": quote.amount_out,
        "slippage_bps": quote.slippage_bps,
        "price_impact": quote.price_impact,
        "route": quote.route_info
    }


@router.post("/jupiter/swap")
async def get_jupiter_swap_transaction(
    request: SwapTransactionRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get a swap transaction from Jupiter for client-side signing"""
    # First get quote
    quote = await jupiter.get_quote(
        input_mint=request.input_mint,
        output_mint=request.output_mint,
        amount=request.amount,
        slippage_bps=request.slippage_bps
    )
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get swap quote"
        )
    
    # Get transaction
    swap_tx = await jupiter.get_swap_transaction(
        quote=quote,
        user_pubkey=request.user_pubkey
    )
    
    if not swap_tx:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get swap transaction"
        )
    
    return {
        "swap_transaction": swap_tx,
        "quote": {
            "amount_in": quote.amount_in,
            "amount_out": quote.amount_out,
            "price_impact": quote.price_impact,
            "route": quote.route_info
        }
    }


# ============================================================
# TOKEN INFO ENDPOINTS
# ============================================================

@router.post("/token/info")
async def get_token_info(
    request: TokenCheckRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get token information from DexScreener"""
    token = await dexscreener.get_token(request.address)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )
    
    return {
        "address": token.address,
        "name": token.name,
        "symbol": token.symbol,
        "price_usd": token.price_usd,
        "liquidity_usd": token.liquidity_usd,
        "volume_5m": token.volume_5m,
        "volume_1h": token.volume_1h,
        "volume_24h": token.volume_24h,
        "price_change_5m": token.price_change_5m,
        "price_change_1h": token.price_change_1h,
        "price_change_24h": token.price_change_24h,
        "fdv": token.fdv,
        "market_cap": token.market_cap,
        "dex": token.dex
    }


@router.post("/token/check")
async def check_token_safety(
    request: TokenCheckRequest,
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Check token for honeypot/rug risks"""
    result = await honeypot_api.check_token(request.address)
    
    return {
        "address": result.address,
        "is_honeypot": result.is_honeypot,
        "risk_level": result.risk_level.value,
        "can_buy": result.can_buy,
        "can_sell": result.can_sell,
        "buy_tax": result.buy_tax,
        "sell_tax": result.sell_tax,
        "issues": result.issues
    }
