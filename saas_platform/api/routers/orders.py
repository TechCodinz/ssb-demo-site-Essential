"""
SSB PRO API - Orders Router
Handles: create order, webhook for payment verification
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from api.config import settings, PLAN_PRICES
from api.routers.license import generate_license_key
from api.routers.referral import credit_referral_commission
from api.database import get_db
from api.models.order import Order
from api.models.license import License
from api.models.user import User

router = APIRouter()


class OrderCreateRequest(BaseModel):
    plan: str
    email: EmailStr
    tx_hash: str
    note: Optional[str] = None


class WebhookPayload(BaseModel):
    tx_hash: str
    verified: bool
    amount: float
    sender: Optional[str] = None


@router.post("/create")
async def create_order(request: OrderCreateRequest, db: Session = Depends(get_db)):
    """Create a new order after payment"""
    order_id = f"ORD-{secrets.token_hex(6).upper()}"
    
    # Check if plan is valid
    if request.plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    expected_amount = PLAN_PRICES[request.plan]
    
    # Check if tx_hash already exists
    if db.query(Order).filter(Order.tx_hash == request.tx_hash).first():
        raise HTTPException(status_code=400, detail="Transaction hash already used")

    new_order = Order(
        order_id=order_id,
        plan=request.plan,
        email=request.email,
        tx_hash=request.tx_hash,
        expected_amount=expected_amount,
        status="pending",
        created_at=datetime.utcnow(),
        note=request.note,
        license_key=None
    )
    
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    return {
        "success": True,
        "order_id": order_id,
        "status": "pending",
        "message": "Order created. Awaiting payment verification."
    }


@router.post("/webhook")
async def payment_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Webhook for payment verification (called by payment processor or admin)"""
    
    # Find order by tx_hash
    order = db.query(Order).filter(Order.tx_hash == payload.tx_hash).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this TX hash")
    
    if not payload.verified:
        order.status = "failed"
        order.failure_reason = "Payment verification failed"
        db.commit()
        return {"success": False, "status": "failed"}
    
    # Verify amount
    if payload.amount < order.expected_amount:
        order.status = "underpaid"
        db.commit()
        return {
            "success": False, 
            "status": "underpaid",
            "expected": order.expected_amount,
            "received": payload.amount
        }
    
    # Issue license
    license_key = generate_license_key(order.plan)
    
    # Calculate expiry (1 month for cloud, lifetime for local)
    if "local" in order.plan:
        expires = datetime.utcnow() + timedelta(days=365 * 100)  # 100 years = lifetime
    else:
        expires = datetime.utcnow() + timedelta(days=30)
    
    new_license = License(
        key=license_key,
        plan=order.plan,
        email=order.email,
        hwid="*",
        activated=False,
        expires=expires,
        issued_at=datetime.utcnow(),
        order_id=order.order_id,
        bound_devices=[],
        cloud_session_id=None
    )
    db.add(new_license)
    
    # Update order
    order.status = "completed"
    order.license_key = license_key
    order.completed_at = datetime.utcnow()
    
    db.commit()
    
    # === REFERRAL COMMISSION ===
    # Find the user who placed this order and credit their referrer
    user = db.query(User).filter(User.email == order.email).first()
    if user:
        order_amount = PLAN_PRICES.get(order.plan, 0)
        commission = credit_referral_commission(
            referred_user_id=user.id,
            order_amount=order_amount,
            order_id=order.order_id,
            db=db
        )
        if commission:
            print(f"[REFERRAL] Credited ${commission:.2f} to referrer of {order.email}")
    
    # Log email request (Email service to be configured in Phase 8)
    print(f"[EMAIL] To: {order.email} | Subject: License Activation | Key: {license_key} | Plan: {order.plan}")
    # background_tasks.add_task(send_license_email, order.email, license_key, order.plan)
    
    return {
        "success": True,
        "status": "completed",
        "license_issued": True,
        "license_key": license_key,
        "expires": expires.isoformat()
    }


@router.get("/{order_id}")
async def get_order(order_id: str, db: Session = Depends(get_db)):
    """Get order status"""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order_id": order.order_id,
        "plan": order.plan,
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "license_issued": order.license_key is not None
    }


@router.get("/")
async def list_orders(email: Optional[str] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    """List orders (admin endpoint)"""
    query = db.query(Order)
    
    if email:
        query = query.filter(Order.email == email)
    if status:
        query = query.filter(Order.status == status)
        
    orders = query.all()
    results = []
    for order in orders:
        results.append({
            "order_id": order.order_id,
            "email": order.email,
            "plan": order.plan,
            "status": order.status,
            "created_at": order.created_at.isoformat()
        })
    
    return {"orders": results, "total": len(results)}
