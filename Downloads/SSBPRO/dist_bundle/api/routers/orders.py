"""
SSB PRO API - Orders Router
Handles: create order, webhook for payment verification
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
import secrets
from datetime import datetime

from api.config import settings
from api.routers.license import licenses_db, generate_license_key

router = APIRouter()

# In-memory orders store
orders_db = {}


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
async def create_order(request: OrderCreateRequest):
    """Create a new order after payment"""
    order_id = f"ORD-{secrets.token_hex(6).upper()}"
    
    # Check if plan is valid
    if request.plan not in settings.PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    expected_amount = settings.PLAN_PRICES[request.plan]
    
    order = {
        "order_id": order_id,
        "plan": request.plan,
        "email": request.email,
        "tx_hash": request.tx_hash,
        "expected_amount": expected_amount,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "note": request.note,
        "license_key": None
    }
    
    orders_db[order_id] = order
    
    return {
        "success": True,
        "order_id": order_id,
        "status": "pending",
        "message": "Order created. Awaiting payment verification."
    }


@router.post("/webhook")
async def payment_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """Webhook for payment verification (called by payment processor or admin)"""
    
    # Find order by tx_hash
    order = None
    order_id = None
    for oid, o in orders_db.items():
        if o["tx_hash"] == payload.tx_hash:
            order = o
            order_id = oid
            break
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this TX hash")
    
    if not payload.verified:
        order["status"] = "failed"
        order["failure_reason"] = "Payment verification failed"
        return {"success": False, "status": "failed"}
    
    # Verify amount
    if payload.amount < order["expected_amount"]:
        order["status"] = "underpaid"
        return {
            "success": False, 
            "status": "underpaid",
            "expected": order["expected_amount"],
            "received": payload.amount
        }
    
    # Issue license
    license_key = generate_license_key(order["plan"])
    
    # Calculate expiry (1 month for cloud, lifetime for local)
    if "local" in order["plan"]:
        from datetime import timedelta
        expires = datetime.utcnow() + timedelta(days=365 * 100)  # 100 years = lifetime
    else:
        from datetime import timedelta
        expires = datetime.utcnow() + timedelta(days=30)
    
    licenses_db[license_key] = {
        "key": license_key,
        "plan": order["plan"],
        "email": order["email"],
        "hwid": "*",
        "activated": False,
        "expires": expires.isoformat(),
        "issued_at": datetime.utcnow().isoformat(),
        "order_id": order_id,
        "bound_devices": [],
        "cloud_session_id": None
    }
    
    # Update order
    order["status"] = "completed"
    order["license_key"] = license_key
    order["completed_at"] = datetime.utcnow().isoformat()
    
    # Send email with license (background task)
    # background_tasks.add_task(send_license_email, order["email"], license_key, order["plan"])
    
    return {
        "success": True,
        "status": "completed",
        "license_issued": True,
        "license_key": license_key,
        "expires": expires.isoformat()
    }


@router.get("/{order_id}")
async def get_order(order_id: str):
    """Get order status"""
    order = orders_db.get(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order_id": order["order_id"],
        "plan": order["plan"],
        "status": order["status"],
        "created_at": order["created_at"],
        "completed_at": order.get("completed_at"),
        "license_issued": order["license_key"] is not None
    }


@router.get("/")
async def list_orders(email: Optional[str] = None, status: Optional[str] = None):
    """List orders (admin endpoint)"""
    results = []
    
    for oid, order in orders_db.items():
        if email and order["email"] != email:
            continue
        if status and order["status"] != status:
            continue
        
        results.append({
            "order_id": oid,
            "email": order["email"],
            "plan": order["plan"],
            "status": order["status"],
            "created_at": order["created_at"]
        })
    
    return {"orders": results, "total": len(results)}
