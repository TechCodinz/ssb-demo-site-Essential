"""
Sol Sniper Bot PRO - Usage Monitoring Service
Track user activity, detect abuse, and manage cloud sessions.
"""
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CloudUser, CloudActivityLog

logger = logging.getLogger(__name__)


# ============================================================
# SESSION STATUS
# ============================================================

class SessionStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class CloudSession:
    """Active cloud session"""
    user_id: str
    email: str
    plan: str
    started_at: datetime
    last_activity: datetime
    status: SessionStatus = SessionStatus.ACTIVE
    
    # Activity counters
    tokens_scanned: int = 0
    trades_triggered: int = 0
    filters_passed: int = 0
    filters_blocked: int = 0
    api_calls: int = 0
    errors: int = 0
    
    # Performance
    avg_confidence: float = 0.0
    confidence_scores: List[float] = field(default_factory=list)
    
    # Connection info
    ip_address: str = ""
    device_id: str = ""


@dataclass
class UsageStats:
    """User usage statistics"""
    total_sessions: int = 0
    total_runtime_hours: float = 0.0
    tokens_scanned: int = 0
    trades_triggered: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    win_rate: float = 0.0
    avg_confidence: float = 0.0
    last_active: Optional[datetime] = None


# ============================================================
# USAGE MONITOR
# ============================================================

class UsageMonitor:
    """
    📊 Cloud Usage Monitoring System
    
    Features:
    - Real-time session tracking
    - Activity logging
    - Abuse detection
    - Rate limiting
    - Performance metrics
    """
    
    # Session limits
    SESSION_TIMEOUT_MINUTES = 30  # Idle timeout
    MAX_CONCURRENT_SESSIONS = 1  # Per user (except ELITE = 2)
    
    # Rate limits (per minute)
    # DEMO gets full rate limits - let them see the power!
    # Only restriction: trades are SIMULATED not real
    RATE_LIMITS = {
        "ELITE": {"scans": 100, "trades": 20, "api_calls": 500},
        "PRO": {"scans": 60, "trades": 12, "api_calls": 300},
        "STANDARD": {"scans": 30, "trades": 7, "api_calls": 150},
        # DEMO = FULL POWER for marketing - show them everything!
        "DEMO": {"scans": 100, "trades": 50, "api_calls": 500}  # Trades are simulated
    }
    
    def __init__(self):
        self.active_sessions: Dict[str, CloudSession] = {}
        self.rate_counters: Dict[str, Dict[str, int]] = {}  # user_id -> counters
        self.rate_counter_reset: Dict[str, datetime] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
    
    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================
    
    async def start_session(
        self,
        user_id: str,
        email: str,
        plan: str,
        ip: str = "",
        device_id: str = ""
    ) -> Tuple[bool, str]:
        """
        Start a new cloud session.
        Blocks if user already has max sessions running.
        """
        # Check for existing sessions
        existing = [
            s for s in self.active_sessions.values()
            if s.user_id == user_id and s.status == SessionStatus.ACTIVE
        ]
        
        max_sessions = 2 if plan == "ELITE" else self.MAX_CONCURRENT_SESSIONS
        
        if len(existing) >= max_sessions:
            return False, f"Maximum {max_sessions} concurrent session(s) allowed. Stop your other session first."
        
        # Create new session
        session = CloudSession(
            user_id=user_id,
            email=email,
            plan=plan,
            started_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            ip_address=ip,
            device_id=device_id
        )
        
        session_key = f"{user_id}_{datetime.utcnow().timestamp()}"
        self.active_sessions[session_key] = session
        
        # Initialize rate counters
        self.rate_counters[user_id] = {"scans": 0, "trades": 0, "api_calls": 0}
        self.rate_counter_reset[user_id] = datetime.utcnow()
        
        logger.info(f"Session started for {email} ({plan})")
        return True, session_key
    
    async def stop_session(self, session_key: str) -> bool:
        """Stop a cloud session"""
        if session_key in self.active_sessions:
            session = self.active_sessions[session_key]
            session.status = SessionStatus.STOPPED
            
            # Calculate runtime
            runtime = (datetime.utcnow() - session.started_at).total_seconds() / 3600
            
            logger.info(f"Session stopped for {session.email}. Runtime: {runtime:.2f}h")
            
            del self.active_sessions[session_key]
            return True
        return False
    
    async def heartbeat(self, session_key: str) -> bool:
        """Update session heartbeat"""
        if session_key in self.active_sessions:
            self.active_sessions[session_key].last_activity = datetime.utcnow()
            self.active_sessions[session_key].status = SessionStatus.ACTIVE
            return True
        return False
    
    def get_session(self, session_key: str) -> Optional[CloudSession]:
        """Get session by key"""
        return self.active_sessions.get(session_key)
    
    def get_user_sessions(self, user_id: str) -> List[CloudSession]:
        """Get all sessions for a user"""
        return [
            s for s in self.active_sessions.values()
            if s.user_id == user_id
        ]
    
    # ============================================================
    # ACTIVITY TRACKING
    # ============================================================
    
    async def record_scan(
        self,
        session_key: str,
        token_address: str,
        confidence: float,
        passed_filter: bool
    ) -> Tuple[bool, str]:
        """Record a token scan"""
        session = self.active_sessions.get(session_key)
        if not session:
            return False, "Session not found"
        
        # Check rate limit
        allowed, msg = self._check_rate_limit(session.user_id, session.plan, "scans")
        if not allowed:
            return False, msg
        
        # Update counters
        session.tokens_scanned += 1
        if passed_filter:
            session.filters_passed += 1
        else:
            session.filters_blocked += 1
        
        # Track confidence
        session.confidence_scores.append(confidence)
        if len(session.confidence_scores) > 100:
            session.confidence_scores.pop(0)
        session.avg_confidence = sum(session.confidence_scores) / len(session.confidence_scores)
        
        session.last_activity = datetime.utcnow()
        
        return True, "OK"
    
    async def record_trade(
        self,
        session_key: str,
        token_address: str,
        action: str,  # BUY, SELL
        amount_sol: float,
        success: bool
    ) -> Tuple[bool, str]:
        """Record a trade"""
        session = self.active_sessions.get(session_key)
        if not session:
            return False, "Session not found"
        
        # Check rate limit
        allowed, msg = self._check_rate_limit(session.user_id, session.plan, "trades")
        if not allowed:
            return False, msg
        
        # Update counters
        session.trades_triggered += 1
        if not success:
            session.errors += 1
        
        session.last_activity = datetime.utcnow()
        
        logger.info(f"Trade recorded: {session.email} {action} {amount_sol} SOL")
        return True, "OK"
    
    async def record_api_call(self, session_key: str) -> Tuple[bool, str]:
        """Record an API call for rate limiting"""
        session = self.active_sessions.get(session_key)
        if not session:
            return True, "OK"  # Allow if no session (might be pre-session call)
        
        allowed, msg = self._check_rate_limit(session.user_id, session.plan, "api_calls")
        if not allowed:
            return False, msg
        
        session.api_calls += 1
        return True, "OK"
    
    async def record_error(self, session_key: str, error: str):
        """Record an error"""
        session = self.active_sessions.get(session_key)
        if session:
            session.errors += 1
            session.last_activity = datetime.utcnow()
            
            if session.errors > 50:
                session.status = SessionStatus.ERROR
                logger.warning(f"Session {session.email} has excessive errors")
    
    # ============================================================
    # RATE LIMITING
    # ============================================================
    
    def _check_rate_limit(
        self,
        user_id: str,
        plan: str,
        action: str
    ) -> Tuple[bool, str]:
        """Check if action is within rate limits"""
        # Reset counters if minute passed
        now = datetime.utcnow()
        last_reset = self.rate_counter_reset.get(user_id, now)
        
        if (now - last_reset).seconds >= 60:
            self.rate_counters[user_id] = {"scans": 0, "trades": 0, "api_calls": 0}
            self.rate_counter_reset[user_id] = now
        
        # Get limits
        limits = self.RATE_LIMITS.get(plan, self.RATE_LIMITS["DEMO"])
        counters = self.rate_counters.get(user_id, {})
        
        current = counters.get(action, 0)
        limit = limits.get(action, 0)
        
        if current >= limit:
            return False, f"Rate limit reached: {limit} {action} per minute"
        
        # Increment counter
        counters[action] = current + 1
        self.rate_counters[user_id] = counters
        
        return True, "OK"
    
    # ============================================================
    # ABUSE DETECTION
    # ============================================================
    
    async def detect_abuse(self, user_id: str) -> Tuple[bool, str]:
        """
        Detect abusive patterns:
        - Running multiple sessions
        - Excessive API calls
        - Rapid IP changes
        """
        sessions = self.get_user_sessions(user_id)
        
        # Check for session abuse
        if len(sessions) > 2:
            return True, "Multiple concurrent sessions detected"
        
        # Check for error spam
        for session in sessions:
            if session.errors > 100:
                return True, "Excessive errors - possible abuse"
        
        return False, ""
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_session_stats(self, session_key: str) -> Optional[dict]:
        """Get current session statistics"""
        session = self.active_sessions.get(session_key)
        if not session:
            return None
        
        runtime_hours = (datetime.utcnow() - session.started_at).total_seconds() / 3600
        
        return {
            "status": session.status.value,
            "started_at": session.started_at.isoformat(),
            "runtime_hours": round(runtime_hours, 2),
            "tokens_scanned": session.tokens_scanned,
            "filters_passed": session.filters_passed,
            "filters_blocked": session.filters_blocked,
            "trades_triggered": session.trades_triggered,
            "errors": session.errors,
            "avg_confidence": round(session.avg_confidence, 2),
            "api_calls": session.api_calls
        }
    
    def get_all_active_sessions(self) -> List[dict]:
        """Get all active sessions (admin view)"""
        return [
            {
                "session_key": key,
                "user_id": s.user_id,
                "email": s.email,
                "plan": s.plan,
                "status": s.status.value,
                "started_at": s.started_at.isoformat(),
                "last_activity": s.last_activity.isoformat(),
                "tokens_scanned": s.tokens_scanned,
                "trades_triggered": s.trades_triggered,
                "ip": s.ip_address
            }
            for key, s in self.active_sessions.items()
        ]
    
    def get_global_stats(self) -> dict:
        """Get global usage statistics"""
        total_sessions = len(self.active_sessions)
        active_sessions = sum(1 for s in self.active_sessions.values() if s.status == SessionStatus.ACTIVE)
        total_scans = sum(s.tokens_scanned for s in self.active_sessions.values())
        total_trades = sum(s.trades_triggered for s in self.active_sessions.values())
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_scans_today": total_scans,
            "total_trades_today": total_trades,
            "avg_confidence": round(
                sum(s.avg_confidence for s in self.active_sessions.values()) / max(total_sessions, 1),
                2
            )
        }
    
    # ============================================================
    # CLEANUP
    # ============================================================
    
    async def start_cleanup(self, interval: int = 60):
        """Start background cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval))
    
    async def _cleanup_loop(self, interval: int):
        """Clean up idle sessions"""
        while True:
            try:
                now = datetime.utcnow()
                timeout = timedelta(minutes=self.SESSION_TIMEOUT_MINUTES)
                
                to_remove = []
                for key, session in self.active_sessions.items():
                    if (now - session.last_activity) > timeout:
                        session.status = SessionStatus.IDLE
                        to_remove.append(key)
                        logger.info(f"Session {session.email} timed out")
                
                for key in to_remove:
                    del self.active_sessions[key]
                    
            except Exception as e:
                logger.error(f"Session cleanup error: {e}")
            
            await asyncio.sleep(interval)


# ============================================================
# GLOBAL INSTANCE
# ============================================================

usage_monitor = UsageMonitor()


async def start_usage_monitor():
    """Initialize the usage monitor"""
    await usage_monitor.start_cleanup(interval=60)
    logger.info("Usage Monitor started")
