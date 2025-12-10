"""
Sol Sniper Bot PRO - RPC Manager
Production-ready load-balanced RPC infrastructure with failover, health checks, and plan-based prioritization.
"""
import asyncio
import time
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import aiohttp
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# RPC CONFIGURATION
# ============================================================

class RPCTier(Enum):
    FREE = "FREE"
    PREMIUM = "PREMIUM"


class RPCStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    RATE_LIMITED = "rate_limited"


@dataclass
class RPCEndpoint:
    """An RPC endpoint configuration"""
    id: str
    name: str
    url: str
    weight: float = 1.0
    is_primary: bool = False
    enabled: bool = True
    max_requests_per_minute: int = 100
    priority: int = 1  # Lower = higher priority
    
    # Runtime stats
    status: RPCStatus = RPCStatus.HEALTHY
    current_requests: int = 0
    total_requests: int = 0
    total_errors: int = 0
    last_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    last_health_check: Optional[datetime] = None
    last_error: Optional[str] = None
    rate_limit_until: Optional[datetime] = None


@dataclass 
class RPCUsageStats:
    """Usage statistics per user/plan"""
    user_id: str
    plan: str
    requests_this_minute: int = 0
    requests_this_hour: int = 0
    requests_today: int = 0
    last_request_at: Optional[datetime] = None


# ============================================================
# RPC MANAGER
# ============================================================

class RPCManager:
    """
    🚀 Production RPC Manager
    
    Features:
    - Load-balanced multi-provider routing
    - Automatic failover on errors
    - Health checks every 30 seconds
    - Rate limit detection and protection
    - Plan-based prioritization (ELITE > PRO > STANDARD > DEMO)
    - Latency-based dynamic routing
    - Zero RPC exposure to frontend
    """
    
    # Plan priority (higher = more priority)
    PLAN_PRIORITY = {
        "ELITE": 4,
        "PRO": 3,
        "STANDARD": 2,
        "DEMO": 1,
        "FREE": 0
    }
    
    def __init__(self):
        self.tier = RPCTier.FREE
        self.endpoints: Dict[str, RPCEndpoint] = {}
        self.usage_stats: Dict[str, RPCUsageStats] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._request_window_start = datetime.utcnow()
        
        # Initialize default endpoints
        self._init_default_endpoints()
        
    def _init_default_endpoints(self):
        """Initialize default RPC endpoints (FREE tier)"""
        # Primary: Helius Free
        helius_url = settings.HELIUS_RPC or "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY"
        self.endpoints["helius"] = RPCEndpoint(
            id="helius",
            name="Helius Free",
            url=helius_url,
            weight=0.6,
            is_primary=True,
            priority=1,
            max_requests_per_minute=100
        )
        
        # Secondary: ANKR Free
        ankr_url = settings.ANKR_RPC or "https://rpc.ankr.com/solana"
        self.endpoints["ankr"] = RPCEndpoint(
            id="ankr",
            name="ANKR Free",
            url=ankr_url,
            weight=0.3,
            is_primary=False,
            priority=2,
            max_requests_per_minute=50
        )
        
        # Fallback: QuickNode Free
        quicknode_url = settings.QUICKNODE_RPC or "https://api.mainnet-beta.solana.com"
        self.endpoints["quicknode"] = RPCEndpoint(
            id="quicknode",
            name="QuickNode Free",
            url=quicknode_url,
            weight=0.1,
            is_primary=False,
            priority=3,
            max_requests_per_minute=30
        )
        
    def set_tier(self, tier: RPCTier):
        """Switch RPC tier (FREE or PREMIUM)"""
        self.tier = tier
        logger.info(f"RPC Tier switched to: {tier.value}")
        
        if tier == RPCTier.PREMIUM:
            # Upgrade to premium endpoints
            self._upgrade_to_premium()
    
    def _upgrade_to_premium(self):
        """Upgrade to premium RPC endpoints"""
        # If premium keys are available, use them
        if settings.HELIUS_RPC_PREMIUM:
            self.endpoints["helius"].url = settings.HELIUS_RPC_PREMIUM
            self.endpoints["helius"].name = "Helius PRO"
            self.endpoints["helius"].max_requests_per_minute = 1000
            
        if settings.TRITON_RPC:
            self.endpoints["triton"] = RPCEndpoint(
                id="triton",
                name="Triton Premium",
                url=settings.TRITON_RPC,
                weight=0.3,
                is_primary=False,
                priority=2,
                max_requests_per_minute=500
            )
            
    # ============================================================
    # ENDPOINT SELECTION
    # ============================================================
    
    def select_endpoint(self, user_id: str = "", plan: str = "DEMO") -> Optional[RPCEndpoint]:
        """
        Select the best RPC endpoint based on:
        1. Health status
        2. Rate limit status
        3. Plan priority
        4. Weighted selection
        5. Latency
        """
        available = []
        
        for endpoint in self.endpoints.values():
            if not endpoint.enabled:
                continue
            if endpoint.status == RPCStatus.DOWN:
                continue
            if endpoint.rate_limit_until and datetime.utcnow() < endpoint.rate_limit_until:
                continue
            if endpoint.current_requests >= endpoint.max_requests_per_minute * 0.9:
                continue  # Near rate limit
                
            available.append(endpoint)
        
        if not available:
            # All endpoints exhausted - use any available
            available = [e for e in self.endpoints.values() if e.enabled]
            if not available:
                return None
        
        # Sort by priority and health
        available.sort(key=lambda e: (
            e.priority,
            0 if e.status == RPCStatus.HEALTHY else 1,
            e.avg_latency_ms
        ))
        
        # For premium plans, always use best endpoint
        plan_priority = self.PLAN_PRIORITY.get(plan, 0)
        if plan_priority >= 3:  # PRO or ELITE
            return available[0]
        
        # For lower plans, use weighted random selection
        total_weight = sum(e.weight for e in available)
        r = random.random() * total_weight
        current = 0
        
        for endpoint in available:
            current += endpoint.weight
            if r <= current:
                return endpoint
                
        return available[0]
    
    # ============================================================
    # RPC REQUESTS
    # ============================================================
    
    async def call(
        self,
        method: str,
        params: list = None,
        user_id: str = "",
        plan: str = "DEMO",
        timeout: float = 10.0
    ) -> Tuple[Optional[dict], Optional[str]]:
        """
        Make an RPC call with automatic failover.
        Returns: (result, error)
        """
        params = params or []
        errors = []
        
        # Try up to 3 different endpoints
        for attempt in range(3):
            endpoint = self.select_endpoint(user_id, plan)
            if not endpoint:
                return None, "No RPC endpoints available"
            
            try:
                start_time = time.time()
                
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": method,
                        "params": params
                    }
                    
                    async with session.post(
                        endpoint.url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        latency = (time.time() - start_time) * 1000
                        
                        # Update stats
                        endpoint.current_requests += 1
                        endpoint.total_requests += 1
                        endpoint.last_latency_ms = latency
                        endpoint.avg_latency_ms = (
                            endpoint.avg_latency_ms * 0.9 + latency * 0.1
                        )
                        
                        # Track user usage
                        self._track_usage(user_id, plan)
                        
                        if resp.status == 429:
                            # Rate limited
                            endpoint.status = RPCStatus.RATE_LIMITED
                            endpoint.rate_limit_until = datetime.utcnow() + timedelta(seconds=60)
                            errors.append(f"{endpoint.name}: Rate limited")
                            continue
                        
                        if resp.status != 200:
                            endpoint.total_errors += 1
                            errors.append(f"{endpoint.name}: HTTP {resp.status}")
                            continue
                        
                        data = await resp.json()
                        
                        if "error" in data:
                            endpoint.total_errors += 1
                            errors.append(f"{endpoint.name}: {data['error']}")
                            continue
                        
                        # Success
                        endpoint.status = RPCStatus.HEALTHY
                        return data.get("result"), None
                        
            except asyncio.TimeoutError:
                endpoint.total_errors += 1
                endpoint.status = RPCStatus.DEGRADED
                errors.append(f"{endpoint.name}: Timeout")
                
            except Exception as e:
                endpoint.total_errors += 1
                endpoint.last_error = str(e)
                errors.append(f"{endpoint.name}: {str(e)}")
        
        return None, "; ".join(errors)
    
    def _track_usage(self, user_id: str, plan: str):
        """Track RPC usage per user"""
        if not user_id:
            return
            
        key = f"{user_id}:{plan}"
        if key not in self.usage_stats:
            self.usage_stats[key] = RPCUsageStats(user_id=user_id, plan=plan)
            
        stats = self.usage_stats[key]
        stats.requests_this_minute += 1
        stats.requests_this_hour += 1
        stats.requests_today += 1
        stats.last_request_at = datetime.utcnow()
    
    # ============================================================
    # HEALTH CHECKS
    # ============================================================
    
    async def start_health_checks(self, interval: int = 30):
        """Start background health check loop"""
        self._health_check_task = asyncio.create_task(
            self._health_check_loop(interval)
        )
        
    async def _health_check_loop(self, interval: int):
        """Background health check loop"""
        while True:
            try:
                await self._run_health_checks()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            await asyncio.sleep(interval)
    
    async def _run_health_checks(self):
        """Run health check on all endpoints"""
        for endpoint in self.endpoints.values():
            if not endpoint.enabled:
                continue
                
            try:
                start_time = time.time()
                
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getLatestBlockhash",
                        "params": [{"commitment": "finalized"}]
                    }
                    
                    async with session.post(
                        endpoint.url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        latency = (time.time() - start_time) * 1000
                        endpoint.last_health_check = datetime.utcnow()
                        endpoint.last_latency_ms = latency
                        
                        if resp.status == 200:
                            data = await resp.json()
                            if "result" in data:
                                endpoint.status = RPCStatus.HEALTHY
                            else:
                                endpoint.status = RPCStatus.DEGRADED
                        else:
                            endpoint.status = RPCStatus.DEGRADED
                            
            except Exception as e:
                endpoint.status = RPCStatus.DOWN
                endpoint.last_error = str(e)
                logger.warning(f"RPC {endpoint.name} health check failed: {e}")
        
        # Reset request counters every minute
        now = datetime.utcnow()
        if (now - self._request_window_start).seconds >= 60:
            for endpoint in self.endpoints.values():
                endpoint.current_requests = 0
            self._request_window_start = now
    
    # ============================================================
    # ADMIN CONTROLS
    # ============================================================
    
    def enable_endpoint(self, endpoint_id: str):
        """Enable an RPC endpoint"""
        if endpoint_id in self.endpoints:
            self.endpoints[endpoint_id].enabled = True
            
    def disable_endpoint(self, endpoint_id: str):
        """Disable an RPC endpoint"""
        if endpoint_id in self.endpoints:
            self.endpoints[endpoint_id].enabled = False
    
    def set_weight(self, endpoint_id: str, weight: float):
        """Set endpoint weight for load balancing"""
        if endpoint_id in self.endpoints:
            self.endpoints[endpoint_id].weight = max(0.01, min(1.0, weight))
            
    def add_endpoint(self, endpoint: RPCEndpoint):
        """Add a new RPC endpoint"""
        self.endpoints[endpoint.id] = endpoint
        
    def remove_endpoint(self, endpoint_id: str):
        """Remove an RPC endpoint"""
        if endpoint_id in self.endpoints:
            del self.endpoints[endpoint_id]
    
    # ============================================================
    # STATS & MONITORING
    # ============================================================
    
    def get_stats(self) -> dict:
        """Get RPC health and usage statistics"""
        endpoints_stats = []
        
        for ep in self.endpoints.values():
            success_rate = (
                (ep.total_requests - ep.total_errors) / ep.total_requests * 100
                if ep.total_requests > 0 else 100
            )
            
            endpoints_stats.append({
                "id": ep.id,
                "name": ep.name,
                "status": ep.status.value,
                "enabled": ep.enabled,
                "is_primary": ep.is_primary,
                "weight": ep.weight,
                "priority": ep.priority,
                "current_requests": ep.current_requests,
                "total_requests": ep.total_requests,
                "total_errors": ep.total_errors,
                "success_rate": round(success_rate, 2),
                "latency_ms": round(ep.avg_latency_ms, 2),
                "last_latency_ms": round(ep.last_latency_ms, 2),
                "last_health_check": ep.last_health_check.isoformat() if ep.last_health_check else None,
                "last_error": ep.last_error
            })
            
        return {
            "tier": self.tier.value,
            "total_endpoints": len(self.endpoints),
            "healthy_endpoints": sum(1 for e in self.endpoints.values() if e.status == RPCStatus.HEALTHY),
            "endpoints": endpoints_stats
        }
    
    def get_top_consumers(self, limit: int = 10) -> List[dict]:
        """Get top RPC consumers for admin"""
        sorted_stats = sorted(
            self.usage_stats.values(),
            key=lambda s: s.requests_today,
            reverse=True
        )[:limit]
        
        return [
            {
                "user_id": s.user_id,
                "plan": s.plan,
                "requests_today": s.requests_today,
                "requests_this_hour": s.requests_this_hour,
                "last_request": s.last_request_at.isoformat() if s.last_request_at else None
            }
            for s in sorted_stats
        ]


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

async def get_latest_blockhash(user_id: str = "", plan: str = "DEMO") -> Optional[str]:
    """Get latest blockhash from Solana"""
    result, error = await rpc_manager.call(
        "getLatestBlockhash",
        [{"commitment": "finalized"}],
        user_id=user_id,
        plan=plan
    )
    
    if result and "value" in result:
        return result["value"]["blockhash"]
    return None


async def get_balance(address: str, user_id: str = "", plan: str = "DEMO") -> Optional[float]:
    """Get SOL balance for an address"""
    result, error = await rpc_manager.call(
        "getBalance",
        [address],
        user_id=user_id,
        plan=plan
    )
    
    if result and "value" in result:
        return result["value"] / 1e9  # lamports to SOL
    return None


async def get_token_accounts(
    owner: str,
    mint: str = None,
    user_id: str = "",
    plan: str = "DEMO"
) -> Optional[list]:
    """Get token accounts for an owner"""
    params = [
        owner,
        {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
        {"encoding": "jsonParsed"}
    ]
    
    if mint:
        params[1] = {"mint": mint}
    
    result, error = await rpc_manager.call(
        "getTokenAccountsByOwner",
        params,
        user_id=user_id,
        plan=plan
    )
    
    if result and "value" in result:
        return result["value"]
    return None


async def send_transaction(
    signed_tx: str,
    user_id: str = "",
    plan: str = "DEMO",
    skip_preflight: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """
    Send a signed transaction to the network.
    Returns: (signature, error)
    """
    params = [
        signed_tx,
        {
            "encoding": "base64",
            "skipPreflight": skip_preflight,
            "preflightCommitment": "confirmed",
            "maxRetries": 3
        }
    ]
    
    result, error = await rpc_manager.call(
        "sendTransaction",
        params,
        user_id=user_id,
        plan=plan,
        timeout=30.0
    )
    
    if error:
        return None, error
    return result, None


# ============================================================
# GLOBAL INSTANCE
# ============================================================

rpc_manager = RPCManager()


async def start_rpc_manager():
    """Initialize and start the RPC manager"""
    await rpc_manager.start_health_checks(interval=30)
    logger.info("RPC Manager started with health checks")
