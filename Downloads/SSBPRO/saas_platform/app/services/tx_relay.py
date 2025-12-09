"""
Sol Sniper Bot PRO - Transaction Relay Service
Receives signed transactions from clients and broadcasts via backend RPC.
Zero private key exposure - all signing happens client-side.
"""
import asyncio
import base64
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import secrets
import logging

from app.services.rpc_manager import rpc_manager, send_transaction

logger = logging.getLogger(__name__)


# ============================================================
# TRANSACTION STATUS
# ============================================================

class TxStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class TransactionRecord:
    """A transaction record"""
    id: str
    user_id: str
    signed_tx: str  # Base64 encoded signed transaction
    signature: Optional[str] = None
    status: TxStatus = TxStatus.PENDING
    error: Optional[str] = None
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Transaction metadata
    tx_type: str = ""  # BUY, SELL, SWAP
    amount_sol: float = 0.0
    token_mint: str = ""
    

@dataclass
class TransactionResult:
    """Result of transaction submission"""
    success: bool
    signature: Optional[str] = None
    error: Optional[str] = None
    confirmations: int = 0


# ============================================================
# TRANSACTION RELAY SERVICE
# ============================================================

class TransactionRelayService:
    """
    🔐 Secure Transaction Relay
    
    Architecture:
    1. Client signs transaction locally (private key never leaves browser)
    2. Client sends signed TX (base64) to this service
    3. Service broadcasts TX via backend RPC
    4. Service returns signature and confirmation status
    
    Security:
    - Zero private key storage
    - Zero private key transmission
    - All signing is client-side only
    - Server only sees signed transaction bytes
    """
    
    # Transaction limits per plan
    TX_LIMITS = {
        "ELITE": {"per_minute": 30, "per_hour": 500, "per_day": 5000},
        "PRO": {"per_minute": 15, "per_hour": 200, "per_day": 2000},
        "STANDARD": {"per_minute": 5, "per_hour": 50, "per_day": 500},
        # DEMO = Simulated only (tracked separately)
        "DEMO": {"per_minute": 0, "per_hour": 0, "per_day": 0}  # No REAL trading
    }
    
    # Simulated trades for DEMO mode
    SIMULATED_TX_LIMITS = {
        "DEMO": {"per_minute": 50, "per_hour": 500, "per_day": 5000}  # Full power for demo!
    }
    
    def __init__(self):
        self.transactions: Dict[str, TransactionRecord] = {}
        self.user_tx_counts: Dict[str, Dict[str, int]] = {}
        self.simulated_transactions: Dict[str, TransactionRecord] = {}  # DEMO simulated trades
        self.simulated_pnl: Dict[str, float] = {}  # Track simulated P&L per user
        self._cleanup_task: Optional[asyncio.Task] = None
        
    # ============================================================
    # RATE LIMITING
    # ============================================================
    
    def check_rate_limit(self, user_id: str, plan: str, simulated: bool = False) -> Tuple[bool, str]:
        """
        Check if user can submit a transaction.
        Returns: (allowed, message)
        """
        # DEMO mode = simulated only
        if plan == "DEMO":
            if not simulated:
                return False, "🎮 DEMO MODE: This trade was SIMULATED. Upgrade to execute real trades!"
            # Check simulated limits (very generous)
            limits = self.SIMULATED_TX_LIMITS.get("DEMO")
        else:
            limits = self.TX_LIMITS.get(plan, self.TX_LIMITS["STANDARD"])
        
        if limits["per_day"] == 0 and not simulated:
            return False, "Live trading not available on your plan. Upgrade to STANDARD or higher."
        
        # Get or create user counts
        if user_id not in self.user_tx_counts:
            self.user_tx_counts[user_id] = {
                "minute": 0,
                "hour": 0,
                "day": 0,
                "last_minute": datetime.utcnow(),
                "last_hour": datetime.utcnow(),
                "last_day": datetime.utcnow()
            }
        
        counts = self.user_tx_counts[user_id]
        now = datetime.utcnow()
        
        # Reset counters if window passed
        if (now - counts["last_minute"]).seconds >= 60:
            counts["minute"] = 0
            counts["last_minute"] = now
        if (now - counts["last_hour"]).seconds >= 3600:
            counts["hour"] = 0
            counts["last_hour"] = now
        if (now - counts["last_day"]).days >= 1:
            counts["day"] = 0
            counts["last_day"] = now
        
        # Check limits
        if counts["minute"] >= limits["per_minute"]:
            return False, f"Rate limit reached: {limits['per_minute']} transactions per minute"
        if counts["hour"] >= limits["per_hour"]:
            return False, f"Rate limit reached: {limits['per_hour']} transactions per hour"
        if counts["day"] >= limits["per_day"]:
            return False, f"Daily limit reached: {limits['per_day']} transactions per day"
        
        return True, "OK"
    
    def increment_count(self, user_id: str):
        """Increment transaction count for user"""
        if user_id in self.user_tx_counts:
            self.user_tx_counts[user_id]["minute"] += 1
            self.user_tx_counts[user_id]["hour"] += 1
            self.user_tx_counts[user_id]["day"] += 1
    
    # ============================================================
    # SIMULATED TRADING (DEMO MODE)
    # ============================================================
    
    async def submit_simulated_trade(
        self,
        user_id: str,
        tx_type: str,
        token_mint: str,
        token_symbol: str,
        amount_sol: float,
        price_usd: float
    ) -> TransactionResult:
        """
        Submit a simulated trade for DEMO mode.
        Tracks P&L without executing real transactions.
        """
        # Create simulated transaction record
        tx_id = f"SIM-{secrets.token_hex(8)}"
        record = TransactionRecord(
            id=tx_id,
            user_id=user_id,
            signed_tx="SIMULATED",
            signature=tx_id,
            tx_type=tx_type,
            token_mint=token_mint,
            amount_sol=amount_sol,
            status=TxStatus.CONFIRMED,  # Simulated = instant confirm
            submitted_at=datetime.utcnow(),
            confirmed_at=datetime.utcnow()
        )
        self.simulated_transactions[tx_id] = record
        self.increment_count(user_id)
        
        # Track simulated P&L
        if user_id not in self.simulated_pnl:
            self.simulated_pnl[user_id] = 0.0
        
        # Generate random simulated profit (for marketing appeal)
        import random
        if tx_type == "SELL":
            # Simulate profit between 5% - 50%
            profit_pct = random.uniform(0.05, 0.50)
            simulated_profit = amount_sol * price_usd * profit_pct
            self.simulated_pnl[user_id] += simulated_profit
        
        logger.info(f"Simulated trade for {user_id}: {tx_type} {amount_sol} SOL ({token_symbol})")
        
        return TransactionResult(
            success=True,
            signature=tx_id,  # Simulated signature
            confirmations=1
        )
    
    def get_simulated_pnl(self, user_id: str) -> dict:
        """Get simulated P&L for a DEMO user"""
        trades = [
            tx for tx in self.simulated_transactions.values()
            if tx.user_id == user_id
        ]
        
        return {
            "total_simulated_trades": len(trades),
            "simulated_pnl_usd": round(self.simulated_pnl.get(user_id, 0.0), 2),
            "message": "🚀 This is your SIMULATED profit! Upgrade to trade LIVE and earn REAL money!"
        }
    
    # ============================================================
    # TRANSACTION SUBMISSION
    # ============================================================
    
    async def submit_transaction(
        self,
        user_id: str,
        plan: str,
        signed_tx_base64: str,
        tx_type: str = "SWAP",
        token_mint: str = "",
        amount_sol: float = 0.0,
        skip_preflight: bool = False
    ) -> TransactionResult:
        """
        Submit a signed transaction to the Solana network.
        
        Args:
            user_id: User ID for rate limiting
            plan: User's plan for limits
            signed_tx_base64: Base64 encoded signed transaction
            tx_type: Transaction type (BUY, SELL, SWAP)
            skip_preflight: Skip preflight checks for faster submission
            
        Returns:
            TransactionResult with signature or error
        """
        # Check rate limit
        allowed, message = self.check_rate_limit(user_id, plan)
        if not allowed:
            return TransactionResult(success=False, error=message)
        
        # Validate transaction format
        try:
            tx_bytes = base64.b64decode(signed_tx_base64)
            if len(tx_bytes) < 100:
                return TransactionResult(success=False, error="Invalid transaction: too short")
        except Exception as e:
            return TransactionResult(success=False, error=f"Invalid base64 encoding: {e}")
        
        # Create transaction record
        tx_id = secrets.token_hex(16)
        record = TransactionRecord(
            id=tx_id,
            user_id=user_id,
            signed_tx=signed_tx_base64,
            tx_type=tx_type,
            token_mint=token_mint,
            amount_sol=amount_sol,
            status=TxStatus.PENDING
        )
        self.transactions[tx_id] = record
        
        try:
            # Submit via RPC manager
            signature, error = await send_transaction(
                signed_tx=signed_tx_base64,
                user_id=user_id,
                plan=plan,
                skip_preflight=skip_preflight
            )
            
            if error:
                record.status = TxStatus.FAILED
                record.error = error
                return TransactionResult(success=False, error=error)
            
            # Success
            record.signature = signature
            record.status = TxStatus.SUBMITTED
            record.submitted_at = datetime.utcnow()
            
            # Increment count
            self.increment_count(user_id)
            
            logger.info(f"Transaction submitted for user {user_id}: {signature}")
            
            return TransactionResult(
                success=True,
                signature=signature
            )
            
        except Exception as e:
            record.status = TxStatus.FAILED
            record.error = str(e)
            logger.error(f"Transaction submission error: {e}")
            return TransactionResult(success=False, error=str(e))
    
    # ============================================================
    # TRANSACTION CONFIRMATION
    # ============================================================
    
    async def confirm_transaction(
        self,
        signature: str,
        user_id: str = "",
        plan: str = "DEMO",
        timeout: int = 30
    ) -> TransactionResult:
        """
        Wait for transaction confirmation.
        
        Args:
            signature: Transaction signature
            timeout: Maximum wait time in seconds
            
        Returns:
            TransactionResult with confirmation status
        """
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).seconds < timeout:
            try:
                result, error = await rpc_manager.call(
                    "getSignatureStatuses",
                    [[signature], {"searchTransactionHistory": True}],
                    user_id=user_id,
                    plan=plan
                )
                
                if result and "value" in result:
                    statuses = result["value"]
                    if statuses and statuses[0]:
                        status = statuses[0]
                        
                        if status.get("err"):
                            # Transaction failed on-chain
                            return TransactionResult(
                                success=False,
                                signature=signature,
                                error=f"Transaction failed: {status.get('err')}"
                            )
                        
                        confirmations = status.get("confirmations") or 0
                        confirmation_status = status.get("confirmationStatus", "")
                        
                        if confirmation_status in ["confirmed", "finalized"]:
                            # Update record
                            for record in self.transactions.values():
                                if record.signature == signature:
                                    record.status = TxStatus.CONFIRMED
                                    record.confirmed_at = datetime.utcnow()
                                    break
                            
                            return TransactionResult(
                                success=True,
                                signature=signature,
                                confirmations=confirmations if confirmations else 1
                            )
                
            except Exception as e:
                logger.error(f"Confirmation check error: {e}")
            
            await asyncio.sleep(1)
        
        return TransactionResult(
            success=False,
            signature=signature,
            error="Confirmation timeout"
        )
    
    async def submit_and_confirm(
        self,
        user_id: str,
        plan: str,
        signed_tx_base64: str,
        tx_type: str = "SWAP",
        token_mint: str = "",
        amount_sol: float = 0.0,
        timeout: int = 30
    ) -> TransactionResult:
        """Submit transaction and wait for confirmation"""
        # Submit
        result = await self.submit_transaction(
            user_id=user_id,
            plan=plan,
            signed_tx_base64=signed_tx_base64,
            tx_type=tx_type,
            token_mint=token_mint,
            amount_sol=amount_sol
        )
        
        if not result.success or not result.signature:
            return result
        
        # Confirm
        return await self.confirm_transaction(
            signature=result.signature,
            user_id=user_id,
            plan=plan,
            timeout=timeout
        )
    
    # ============================================================
    # TRANSACTION HISTORY
    # ============================================================
    
    def get_user_transactions(
        self,
        user_id: str,
        limit: int = 50,
        status: Optional[TxStatus] = None
    ) -> List[dict]:
        """Get transaction history for a user"""
        transactions = [
            tx for tx in self.transactions.values()
            if tx.user_id == user_id
        ]
        
        if status:
            transactions = [tx for tx in transactions if tx.status == status]
        
        # Sort by created_at descending
        transactions.sort(key=lambda x: x.created_at, reverse=True)
        
        return [
            {
                "id": tx.id,
                "signature": tx.signature,
                "status": tx.status.value,
                "tx_type": tx.tx_type,
                "token_mint": tx.token_mint,
                "amount_sol": tx.amount_sol,
                "error": tx.error,
                "submitted_at": tx.submitted_at.isoformat() if tx.submitted_at else None,
                "confirmed_at": tx.confirmed_at.isoformat() if tx.confirmed_at else None,
                "created_at": tx.created_at.isoformat()
            }
            for tx in transactions[:limit]
        ]
    
    def get_user_stats(self, user_id: str) -> dict:
        """Get transaction statistics for a user"""
        transactions = [tx for tx in self.transactions.values() if tx.user_id == user_id]
        
        confirmed = sum(1 for tx in transactions if tx.status == TxStatus.CONFIRMED)
        failed = sum(1 for tx in transactions if tx.status == TxStatus.FAILED)
        pending = sum(1 for tx in transactions if tx.status in [TxStatus.PENDING, TxStatus.SUBMITTED])
        
        counts = self.user_tx_counts.get(user_id, {})
        
        return {
            "total_transactions": len(transactions),
            "confirmed": confirmed,
            "failed": failed,
            "pending": pending,
            "success_rate": (confirmed / len(transactions) * 100) if transactions else 0,
            "today_count": counts.get("day", 0),
            "hour_count": counts.get("hour", 0)
        }
    
    # ============================================================
    # CLEANUP
    # ============================================================
    
    async def start_cleanup(self, interval: int = 3600):
        """Start background cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval))
    
    async def _cleanup_loop(self, interval: int):
        """Clean up old transaction records"""
        while True:
            try:
                cutoff = datetime.utcnow() - timedelta(days=7)
                
                to_remove = [
                    tx_id for tx_id, tx in self.transactions.items()
                    if tx.created_at < cutoff
                ]
                
                for tx_id in to_remove:
                    del self.transactions[tx_id]
                
                if to_remove:
                    logger.info(f"Cleaned up {len(to_remove)} old transaction records")
                    
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            
            await asyncio.sleep(interval)


# ============================================================
# GLOBAL INSTANCE
# ============================================================

tx_relay = TransactionRelayService()


async def start_tx_relay():
    """Initialize the transaction relay service"""
    await tx_relay.start_cleanup(interval=3600)
    logger.info("Transaction Relay Service started")
