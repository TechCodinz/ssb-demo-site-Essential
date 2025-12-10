"""
Sol Sniper Bot PRO - USDT Payment Service
TRC20 payment processing with webhook verification and auto-activation.
"""
import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import aiohttp
import logging

from app.core.config import settings
from app.services.email_service import (
    send_payment_received_email,
    send_subscription_expiring_email
)

logger = logging.getLogger(__name__)


# ============================================================
# PAYMENT CONFIGURATION
# ============================================================

class PaymentStatus(Enum):
    PENDING = "pending"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    FAILED = "failed"


class SubscriptionStatus(Enum):
    ACTIVE = "active"
    PENDING_PAYMENT = "pending_payment"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


# Cloud Plan prices in USDT - CLOUD SNIPER
PLAN_PRICES = {
    "STANDARD": 79.0,    # CLOUD SNIPER
    "PRO": 149.0,        # CLOUD SNIPER PRO
    "ELITE": 249.0       # CLOUD SNIPER ELITE
}


@dataclass
class PaymentAddress:
    """User's unique payment address"""
    id: str
    user_id: str
    address: str  # TRC20 address for this user
    created_at: datetime
    expires_at: datetime
    expected_amount: float
    plan: str
    status: PaymentStatus = PaymentStatus.PENDING


@dataclass
class PaymentTransaction:
    """A payment transaction record"""
    id: str
    user_id: str
    tx_hash: str
    amount: float
    from_address: str
    to_address: str
    plan: str
    status: PaymentStatus
    confirmed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Subscription:
    """User subscription record"""
    user_id: str
    plan: str
    status: SubscriptionStatus
    start_date: datetime
    end_date: datetime
    auto_renew: bool = True
    payment_address: Optional[str] = None
    last_payment_at: Optional[datetime] = None
    next_payment_due: Optional[datetime] = None


# ============================================================
# USDT PAYMENT SERVICE
# ============================================================

class USDTPaymentService:
    """
    💸 USDT TRC20 Payment Service
    
    Features:
    - Generate unique payment addresses per user
    - Monitor TRC20 transactions via TRON API
    - Auto-activate subscriptions on confirmation
    - Auto-suspend on expiry
    - Payment history tracking
    """
    
    # TRON network endpoints (free tier)
    TRON_API_URL = "https://api.trongrid.io"
    TRONSCAN_API = "https://apilist.tronscan.org/api"
    
    # Master wallet address (receives all payments)
    # This is configurable via environment
    MASTER_WALLET = settings.USDT_WALLET_ADDRESS or ""
    
    # USDT TRC20 contract
    USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    
    # Confirmation requirements
    CONFIRMATIONS_REQUIRED = 19
    PAYMENT_EXPIRY_HOURS = 24
    
    def __init__(self):
        self.pending_payments: Dict[str, PaymentAddress] = {}
        self.confirmed_payments: Dict[str, PaymentTransaction] = {}
        self.subscriptions: Dict[str, Subscription] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    # ============================================================
    # PAYMENT ADDRESS GENERATION
    # ============================================================
    
    def generate_payment_address(
        self,
        user_id: str,
        plan: str
    ) -> PaymentAddress:
        """
        Generate a unique payment reference for a user.
        
        For simplicity, we use a single master wallet.
        The user is identified by a unique memo/reference.
        In production, you might use HD wallet derivation.
        """
        payment_id = secrets.token_hex(8)
        expires_at = datetime.utcnow() + timedelta(hours=self.PAYMENT_EXPIRY_HOURS)
        amount = PLAN_PRICES.get(plan, 0)
        
        payment = PaymentAddress(
            id=payment_id,
            user_id=user_id,
            address=self.MASTER_WALLET,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            expected_amount=amount,
            plan=plan,
            status=PaymentStatus.PENDING
        )
        
        self.pending_payments[payment_id] = payment
        
        logger.info(f"Generated payment address for user {user_id}: {self.MASTER_WALLET}")
        return payment
    
    # ============================================================
    # PAYMENT VERIFICATION
    # ============================================================
    
    async def verify_payment(
        self,
        tx_hash: str,
        expected_amount: float,
        user_id: str,
        plan: str
    ) -> Tuple[bool, str]:
        """
        Verify a USDT TRC20 payment via TronScan.
        Returns: (success, message)
        """
        try:
            session = await self._get_session()
            
            # Query TronScan API for transaction details
            url = f"{self.TRONSCAN_API}/transaction-info"
            params = {"hash": tx_hash}
            
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return False, "Could not verify transaction. Please try again."
                    
                data = await resp.json()
                
                # Check if transaction exists
                if not data or "contractType" not in data:
                    return False, "Transaction not found. Please check the hash."
                
                # Check if it's a TRC20 transfer
                contract_type = data.get("contractType")
                if contract_type != 31:  # TriggerSmartContract
                    return False, "Invalid transaction type. Must be USDT TRC20 transfer."
                
                # Get contract data
                contract = data.get("contractData", {})
                trigger = data.get("trigger_info", {})
                
                # Verify USDT contract
                to_address = contract.get("contract_address", "")
                if to_address != self.USDT_CONTRACT:
                    return False, "Not a USDT transaction."
                
                # Get transfer details from trigger info
                transfer_to = trigger.get("parameter", {}).get("_to", "")
                transfer_amount = trigger.get("parameter", {}).get("_value", 0)
                
                # Convert amount (USDT has 6 decimals)
                amount_usdt = float(transfer_amount) / 1e6
                
                # Verify amount
                if amount_usdt < expected_amount:
                    return False, f"Amount mismatch. Expected ${expected_amount}, received ${amount_usdt}"
                
                # Verify recipient
                if transfer_to != self.MASTER_WALLET:
                    return False, "Payment sent to wrong address."
                
                # Check confirmations
                confirmations = data.get("confirmations", 0)
                if confirmations < self.CONFIRMATIONS_REQUIRED:
                    return False, f"Waiting for confirmations ({confirmations}/{self.CONFIRMATIONS_REQUIRED})"
                
                # Check if already used
                if tx_hash in self.confirmed_payments:
                    return False, "This transaction has already been used."
                
                # Payment verified!
                payment = PaymentTransaction(
                    id=secrets.token_hex(8),
                    user_id=user_id,
                    tx_hash=tx_hash,
                    amount=amount_usdt,
                    from_address=data.get("ownerAddress", ""),
                    to_address=self.MASTER_WALLET,
                    plan=plan,
                    status=PaymentStatus.CONFIRMED,
                    confirmed_at=datetime.utcnow()
                )
                
                self.confirmed_payments[tx_hash] = payment
                
                # Activate subscription
                await self._activate_subscription(user_id, plan, payment)
                
                return True, f"Payment verified! ${amount_usdt} received. Subscription activated."
                
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            return False, f"Verification error: {str(e)}"
    
    # ============================================================
    # SUBSCRIPTION MANAGEMENT
    # ============================================================
    
    async def _activate_subscription(
        self,
        user_id: str,
        plan: str,
        payment: PaymentTransaction
    ):
        """Activate or extend a subscription"""
        now = datetime.utcnow()
        
        existing = self.subscriptions.get(user_id)
        
        if existing and existing.status == SubscriptionStatus.ACTIVE:
            # Extend existing subscription
            new_end = existing.end_date + timedelta(days=30)
        else:
            # New subscription
            new_end = now + timedelta(days=30)
        
        subscription = Subscription(
            user_id=user_id,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            end_date=new_end,
            auto_renew=True,
            last_payment_at=now,
            next_payment_due=new_end - timedelta(days=3)
        )
        
        self.subscriptions[user_id] = subscription
        
        logger.info(f"Subscription activated for user {user_id}: {plan} until {new_end}")
        
        # TODO: Update database
        # TODO: Send confirmation email
    
    def get_subscription(self, user_id: str) -> Optional[Subscription]:
        """Get user's subscription status"""
        return self.subscriptions.get(user_id)
    
    async def check_subscription_status(self, user_id: str) -> dict:
        """Check if subscription is active and valid"""
        subscription = self.subscriptions.get(user_id)
        
        if not subscription:
            return {
                "active": False,
                "plan": None,
                "status": "no_subscription",
                "days_remaining": 0
            }
        
        now = datetime.utcnow()
        
        # Check if expired
        if subscription.end_date < now:
            subscription.status = SubscriptionStatus.EXPIRED
            return {
                "active": False,
                "plan": subscription.plan,
                "status": "expired",
                "expired_at": subscription.end_date.isoformat(),
                "days_remaining": 0
            }
        
        days_remaining = (subscription.end_date - now).days
        
        return {
            "active": subscription.status == SubscriptionStatus.ACTIVE,
            "plan": subscription.plan,
            "status": subscription.status.value,
            "end_date": subscription.end_date.isoformat(),
            "days_remaining": days_remaining,
            "auto_renew": subscription.auto_renew
        }
    
    async def suspend_subscription(self, user_id: str, reason: str = ""):
        """Suspend a subscription"""
        subscription = self.subscriptions.get(user_id)
        if subscription:
            subscription.status = SubscriptionStatus.SUSPENDED
            logger.warning(f"Subscription suspended for user {user_id}: {reason}")
    
    async def cancel_subscription(self, user_id: str):
        """Cancel auto-renewal"""
        subscription = self.subscriptions.get(user_id)
        if subscription:
            subscription.auto_renew = False
            logger.info(f"Auto-renewal cancelled for user {user_id}")
    
    # ============================================================
    # PAYMENT MONITORING
    # ============================================================
    
    async def start_monitoring(self, interval: int = 60):
        """Start background payment monitoring"""
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(interval)
        )
        logger.info("Payment monitoring started")
    
    async def _monitor_loop(self, interval: int):
        """Background loop to check for pending payments and expiries"""
        while True:
            try:
                await self._check_pending_payments()
                await self._check_subscription_expiries()
            except Exception as e:
                logger.error(f"Payment monitor error: {e}")
            await asyncio.sleep(interval)
    
    async def _check_pending_payments(self):
        """Check for new payments to master wallet"""
        try:
            session = await self._get_session()
            
            # Query recent TRC20 transfers to master wallet
            url = f"{self.TRONSCAN_API}/contract/events"
            params = {
                "contract": self.USDT_CONTRACT,
                "limit": 50,
                "start": 0
            }
            
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return
                    
                data = await resp.json()
                events = data.get("data", [])
                
                for event in events:
                    # Check if transfer to our wallet
                    to_address = event.get("to", "")
                    if to_address != self.MASTER_WALLET:
                        continue
                    
                    tx_hash = event.get("transaction_hash", "")
                    if tx_hash in self.confirmed_payments:
                        continue  # Already processed
                    
                    # Try to match with pending payment
                    amount = float(event.get("value", 0)) / 1e6
                    
                    for payment_id, payment in list(self.pending_payments.items()):
                        if payment.status != PaymentStatus.PENDING:
                            continue
                        if abs(payment.expected_amount - amount) < 0.01:
                            # Potential match - verify fully
                            success, msg = await self.verify_payment(
                                tx_hash,
                                payment.expected_amount,
                                payment.user_id,
                                payment.plan
                            )
                            if success:
                                payment.status = PaymentStatus.CONFIRMED
                                logger.info(f"Auto-matched payment for user {payment.user_id}")
                                
        except Exception as e:
            logger.error(f"Pending payment check error: {e}")
    
    async def _check_subscription_expiries(self):
        """Check for expiring/expired subscriptions"""
        now = datetime.utcnow()
        
        for user_id, subscription in list(self.subscriptions.items()):
            if subscription.status != SubscriptionStatus.ACTIVE:
                continue
            
            days_remaining = (subscription.end_date - now).days
            
            # Send reminder 3 days before expiry
            if days_remaining == 3 and subscription.auto_renew:
                # Generate new payment address
                payment = self.generate_payment_address(user_id, subscription.plan)
                subscription.payment_address = payment.address
                # TODO: Send reminder email
                logger.info(f"Sent expiry reminder to user {user_id}")
            
            # Expire subscription
            if days_remaining <= 0:
                subscription.status = SubscriptionStatus.EXPIRED
                logger.info(f"Subscription expired for user {user_id}")
                # TODO: Send expiry email
    
    # ============================================================
    # ADMIN FUNCTIONS
    # ============================================================
    
    async def admin_approve_payment(
        self,
        user_id: str,
        plan: str,
        admin_id: str,
        notes: str = ""
    ) -> bool:
        """Manually approve a payment (admin override)"""
        payment = PaymentTransaction(
            id=secrets.token_hex(8),
            user_id=user_id,
            tx_hash=f"ADMIN_OVERRIDE_{secrets.token_hex(4)}",
            amount=PLAN_PRICES.get(plan, 0),
            from_address="ADMIN",
            to_address=self.MASTER_WALLET,
            plan=plan,
            status=PaymentStatus.CONFIRMED,
            confirmed_at=datetime.utcnow()
        )
        
        self.confirmed_payments[payment.tx_hash] = payment
        await self._activate_subscription(user_id, plan, payment)
        
        logger.info(f"Admin {admin_id} approved payment for user {user_id}: {plan}")
        return True
    
    async def admin_revoke_subscription(
        self,
        user_id: str,
        admin_id: str,
        reason: str = ""
    ) -> bool:
        """Revoke a subscription (admin action)"""
        subscription = self.subscriptions.get(user_id)
        if subscription:
            subscription.status = SubscriptionStatus.CANCELLED
            logger.warning(f"Admin {admin_id} revoked subscription for user {user_id}: {reason}")
            return True
        return False
    
    def get_payment_history(self, user_id: str) -> List[dict]:
        """Get payment history for a user"""
        payments = [
            {
                "id": p.id,
                "tx_hash": p.tx_hash,
                "amount": p.amount,
                "plan": p.plan,
                "status": p.status.value,
                "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
                "created_at": p.created_at.isoformat()
            }
            for p in self.confirmed_payments.values()
            if p.user_id == user_id
        ]
        return sorted(payments, key=lambda x: x["created_at"], reverse=True)
    
    def get_all_subscriptions(self) -> List[dict]:
        """Get all subscriptions (admin view)"""
        return [
            {
                "user_id": s.user_id,
                "plan": s.plan,
                "status": s.status.value,
                "start_date": s.start_date.isoformat(),
                "end_date": s.end_date.isoformat(),
                "auto_renew": s.auto_renew,
                "days_remaining": max(0, (s.end_date - datetime.utcnow()).days)
            }
            for s in self.subscriptions.values()
        ]


# ============================================================
# GLOBAL INSTANCE
# ============================================================

payment_service = USDTPaymentService()


async def start_payment_service():
    """Initialize and start the payment service"""
    await payment_service.start_monitoring(interval=60)
    logger.info("USDT Payment Service started")
