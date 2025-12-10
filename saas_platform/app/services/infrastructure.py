"""
Sol Sniper Bot PRO - Cloud Infrastructure Services
Centralized API handlers for DexScreener, Honeypot detection, Jupiter swaps, and Pump.fun streaming.
All hidden from frontend - users never see API keys or endpoints.
"""
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# DEXSCREENER API
# ============================================================

@dataclass
class TokenInfo:
    """Token information from DexScreener"""
    address: str
    name: str = ""
    symbol: str = ""
    price_usd: float = 0.0
    price_sol: float = 0.0
    liquidity_usd: float = 0.0
    volume_5m: float = 0.0
    volume_1h: float = 0.0
    volume_24h: float = 0.0
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    fdv: float = 0.0
    market_cap: float = 0.0
    pair_address: str = ""
    dex: str = ""
    created_at: Optional[datetime] = None
    

class DexScreenerAPI:
    """
    DexScreener API Handler
    
    Provides token data, price, liquidity, and volume information.
    All requests go through backend - never exposed to frontend.
    """
    
    BASE_URL = "https://api.dexscreener.com"
    CACHE_TTL = 60  # Cache for 60 seconds
    
    def __init__(self):
        self.cache: Dict[str, Tuple[TokenInfo, datetime]] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def get_token(self, address: str) -> Optional[TokenInfo]:
        """Get token information by address"""
        # Check cache
        if address in self.cache:
            info, cached_at = self.cache[address]
            if (datetime.utcnow() - cached_at).seconds < self.CACHE_TTL:
                return info
        
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/latest/dex/tokens/{address}"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                    
                data = await resp.json()
                pairs = data.get("pairs", [])
                
                if not pairs:
                    return None
                    
                # Get the best pair (highest liquidity)
                pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))
                
                info = TokenInfo(
                    address=address,
                    name=pair.get("baseToken", {}).get("name", ""),
                    symbol=pair.get("baseToken", {}).get("symbol", ""),
                    price_usd=float(pair.get("priceUsd", 0) or 0),
                    liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0) or 0),
                    volume_5m=float(pair.get("volume", {}).get("m5", 0) or 0),
                    volume_1h=float(pair.get("volume", {}).get("h1", 0) or 0),
                    volume_24h=float(pair.get("volume", {}).get("h24", 0) or 0),
                    price_change_5m=float(pair.get("priceChange", {}).get("m5", 0) or 0),
                    price_change_1h=float(pair.get("priceChange", {}).get("h1", 0) or 0),
                    price_change_24h=float(pair.get("priceChange", {}).get("h24", 0) or 0),
                    fdv=float(pair.get("fdv", 0) or 0),
                    market_cap=float(pair.get("marketCap", 0) or 0),
                    pair_address=pair.get("pairAddress", ""),
                    dex=pair.get("dexId", "")
                )
                
                # Cache result
                self.cache[address] = (info, datetime.utcnow())
                return info
                
        except Exception as e:
            logger.error(f"DexScreener error for {address}: {e}")
            return None
    
    async def get_new_pairs(self, chain: str = "solana") -> List[TokenInfo]:
        """Get newly created pairs"""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/token-profiles/latest/v1"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                    
                data = await resp.json()
                tokens = []
                
                for item in data[:50]:  # Limit to 50
                    if item.get("chainId") == chain:
                        tokens.append(TokenInfo(
                            address=item.get("tokenAddress", ""),
                            name=item.get("name", ""),
                            symbol=item.get("symbol", "")
                        ))
                
                return tokens
                
        except Exception as e:
            logger.error(f"DexScreener new pairs error: {e}")
            return []


# ============================================================
# HONEYPOT DETECTION
# ============================================================

class HoneypotRisk(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HoneypotResult:
    """Honeypot scan result"""
    address: str
    is_honeypot: bool
    risk_level: HoneypotRisk
    buy_tax: float = 0.0
    sell_tax: float = 0.0
    transfer_tax: float = 0.0
    can_buy: bool = True
    can_sell: bool = True
    max_buy: Optional[float] = None
    max_sell: Optional[float] = None
    issues: List[str] = field(default_factory=list)


class HoneypotAPI:
    """
    Honeypot Detection API
    
    Scans tokens for potential scams:
    - High taxes (buy/sell)
    - Disabled selling
    - Hidden functions
    - Owner controls
    """
    
    # Using Solana-specific honeypot detection
    RUGCHECK_URL = "https://api.rugcheck.xyz/v1"
    
    def __init__(self):
        self.cache: Dict[str, Tuple[HoneypotResult, datetime]] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def check_token(self, address: str) -> HoneypotResult:
        """Check if a token is a honeypot"""
        # Check cache (valid for 5 minutes)
        if address in self.cache:
            result, cached_at = self.cache[address]
            if (datetime.utcnow() - cached_at).seconds < 300:
                return result
        
        try:
            session = await self._get_session()
            url = f"{self.RUGCHECK_URL}/tokens/{address}/report"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return self._create_unknown_result(address)
                    
                data = await resp.json()
                
                # Parse rugcheck response
                risks = data.get("risks", [])
                score = data.get("score", 0)
                
                issues = []
                for risk in risks:
                    issues.append(risk.get("name", "Unknown risk"))
                
                # Determine risk level based on score
                if score >= 80:
                    risk_level = HoneypotRisk.SAFE
                    is_honeypot = False
                elif score >= 60:
                    risk_level = HoneypotRisk.LOW
                    is_honeypot = False
                elif score >= 40:
                    risk_level = HoneypotRisk.MEDIUM
                    is_honeypot = False
                elif score >= 20:
                    risk_level = HoneypotRisk.HIGH
                    is_honeypot = True
                else:
                    risk_level = HoneypotRisk.CRITICAL
                    is_honeypot = True
                
                result = HoneypotResult(
                    address=address,
                    is_honeypot=is_honeypot,
                    risk_level=risk_level,
                    issues=issues,
                    can_buy=True,
                    can_sell=not is_honeypot
                )
                
                self.cache[address] = (result, datetime.utcnow())
                return result
                
        except Exception as e:
            logger.error(f"Honeypot check error for {address}: {e}")
            return self._create_unknown_result(address)
    
    def _create_unknown_result(self, address: str) -> HoneypotResult:
        """Create a result when check fails"""
        return HoneypotResult(
            address=address,
            is_honeypot=False,
            risk_level=HoneypotRisk.MEDIUM,
            issues=["Unable to verify - proceed with caution"]
        )


# ============================================================
# JUPITER SWAP API
# ============================================================

@dataclass
class SwapQuote:
    """Jupiter swap quote"""
    input_mint: str
    output_mint: str
    amount_in: int
    amount_out: int
    slippage_bps: int
    price_impact: float
    route_info: str
    swap_data: Optional[dict] = None


class JupiterAPI:
    """
    Jupiter Aggregator API
    
    Provides optimal swap routing across all Solana DEXes.
    Uses priority fee routing for faster execution.
    """
    
    BASE_URL = "https://quote-api.jup.ag/v6"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.use_priority_fees = True
        self.default_slippage_bps = 100  # 1%
        
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = None
    ) -> Optional[SwapQuote]:
        """Get swap quote from Jupiter"""
        try:
            session = await self._get_session()
            slippage = slippage_bps or self.default_slippage_bps
            
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": str(slippage),
                "onlyDirectRoutes": "false",
                "asLegacyTransaction": "false"
            }
            
            url = f"{self.BASE_URL}/quote"
            
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"Jupiter quote error: {error}")
                    return None
                    
                data = await resp.json()
                
                route_plan = data.get("routePlan", [])
                route_info = " → ".join([
                    step.get("swapInfo", {}).get("label", "Unknown")
                    for step in route_plan
                ])
                
                return SwapQuote(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount_in=int(data.get("inAmount", 0)),
                    amount_out=int(data.get("outAmount", 0)),
                    slippage_bps=slippage,
                    price_impact=float(data.get("priceImpactPct", 0)),
                    route_info=route_info or "Direct",
                    swap_data=data
                )
                
        except Exception as e:
            logger.error(f"Jupiter quote error: {e}")
            return None
    
    async def get_swap_transaction(
        self,
        quote: SwapQuote,
        user_pubkey: str,
        priority_fee: int = None
    ) -> Optional[str]:
        """
        Get swap transaction from Jupiter.
        Returns base64 encoded transaction for client-side signing.
        """
        if not quote.swap_data:
            return None
            
        try:
            session = await self._get_session()
            
            body = {
                "quoteResponse": quote.swap_data,
                "userPublicKey": user_pubkey,
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True
            }
            
            # Add priority fee if enabled
            if self.use_priority_fees and priority_fee:
                body["prioritizationFeeLamports"] = priority_fee
            elif self.use_priority_fees:
                body["prioritizationFeeLamports"] = "auto"
            
            url = f"{self.BASE_URL}/swap"
            
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"Jupiter swap error: {error}")
                    return None
                    
                data = await resp.json()
                return data.get("swapTransaction")
                
        except Exception as e:
            logger.error(f"Jupiter swap transaction error: {e}")
            return None
    
    async def get_sol_price(self) -> float:
        """Get current SOL price in USD"""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/price?ids=So11111111111111111111111111111111111111112"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get("data", {}).get("So11111111111111111111111111111111111111112", {}).get("price", 0))
        except:
            pass
        return 0.0


# ============================================================
# PUMP.FUN WEBSOCKET STREAM
# ============================================================

@dataclass
class PumpToken:
    """New token from Pump.fun"""
    mint: str
    name: str
    symbol: str
    uri: str
    creator: str
    market_cap: float
    timestamp: datetime


class PumpFunStream:
    """
    Pump.fun WebSocket Stream Handler
    
    Connects to Pump.fun real-time token stream.
    Broadcasts new tokens to connected cloud engines.
    """
    
    PUMP_WS_URL = "wss://pumpportal.fun/api/data"
    
    def __init__(self):
        self.is_running = False
        self.subscribers: List[asyncio.Queue] = []
        self.recent_tokens: List[PumpToken] = []
        self._reconnect_delay = 1
        self._task: Optional[asyncio.Task] = None
        
    def subscribe(self) -> asyncio.Queue:
        """Subscribe to new token events"""
        queue = asyncio.Queue(maxsize=100)
        self.subscribers.append(queue)
        return queue
    
    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from events"""
        if queue in self.subscribers:
            self.subscribers.remove(queue)
    
    async def start(self):
        """Start the stream"""
        if self.is_running:
            return
            
        self.is_running = True
        self._task = asyncio.create_task(self._run_stream())
        logger.info("Pump.fun stream started")
    
    async def stop(self):
        """Stop the stream"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Pump.fun stream stopped")
    
    async def _run_stream(self):
        """Main stream loop with auto-reconnect"""
        import websockets
        
        while self.is_running:
            try:
                async with websockets.connect(self.PUMP_WS_URL) as ws:
                    # Subscribe to new tokens
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    logger.info("Connected to Pump.fun stream")
                    self._reconnect_delay = 1
                    
                    async for message in ws:
                        if not self.is_running:
                            break
                            
                        try:
                            data = json.loads(message)
                            mint = data.get("mint")
                            
                            if not mint:
                                continue
                            
                            token = PumpToken(
                                mint=mint,
                                name=data.get("name", ""),
                                symbol=data.get("symbol", ""),
                                uri=data.get("uri", ""),
                                creator=data.get("traderPublicKey", ""),
                                market_cap=float(data.get("marketCapSol", 0)),
                                timestamp=datetime.utcnow()
                            )
                            
                            # Store recent tokens
                            self.recent_tokens.append(token)
                            if len(self.recent_tokens) > 1000:
                                self.recent_tokens.pop(0)
                            
                            # Broadcast to subscribers
                            await self._broadcast(token)
                            
                        except Exception as e:
                            logger.error(f"Error processing pump message: {e}")
                            
            except Exception as e:
                if self.is_running:
                    logger.warning(f"Pump.fun stream error: {e}. Reconnecting in {self._reconnect_delay}s...")
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 60)
    
    async def _broadcast(self, token: PumpToken):
        """Broadcast token to all subscribers"""
        dead_queues = []
        
        for queue in self.subscribers:
            try:
                queue.put_nowait(token)
            except asyncio.QueueFull:
                dead_queues.append(queue)
        
        # Remove dead queues
        for q in dead_queues:
            self.subscribers.remove(q)
    
    def get_recent_tokens(self, limit: int = 50) -> List[PumpToken]:
        """Get recent tokens"""
        return self.recent_tokens[-limit:]


# ============================================================
# GLOBAL INSTANCES
# ============================================================

dexscreener = DexScreenerAPI()
honeypot_api = HoneypotAPI()
jupiter = JupiterAPI()
pump_stream = PumpFunStream()


async def start_infrastructure():
    """Start all infrastructure services"""
    await pump_stream.start()
    logger.info("All infrastructure services started")


async def stop_infrastructure():
    """Stop all infrastructure services"""
    await pump_stream.stop()
    logger.info("All infrastructure services stopped")
