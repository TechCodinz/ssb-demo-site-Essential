import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

import requests
import websockets

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
import base58
from license_manager import validate_license  # uses license.ssb for LIVE mode

# =========================
#  PATHS, LOGS, CONFIG
# =========================

CONFIG_PATH = "config.json"
SAMPLE_CONFIG_PATH = "config.sample.json"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
)

logger = logging.getLogger("ssb")


def load_config() -> Dict[str, Any]:
    """
    Load config.json.
    If missing but config.sample.json exists:
        - create config.json from sample
        - return that as defaults (beginner-friendly)
    """
    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(SAMPLE_CONFIG_PATH):
            logger.warning(
                "config.json not found. Creating from config.sample.json for you..."
            )
            with open(SAMPLE_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            try:
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
                logger.info("config.json created from config.sample.json.")
            except Exception as e:
                logger.error(f"Failed to write config.json: {e}")
            return cfg
        else:
            logger.error(
                "config.json not found and config.sample.json missing.\n"
                "Please create config.json before running the bot."
            )
            raise SystemExit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


config = load_config()

# Base config values (before engine tuning)
RPC = config.get("rpc", "").strip()
BUY_AMOUNT = float(config.get("buy_amount_sol", 0.25))
MIN_LIQUIDITY = float(config.get("min_liquidity_usd", 8000))
MIN_VOLUME_5M = float(config.get("min_volume_5m", 15000))
TP = float(config.get("take_profit_percent", 250))
SL = float(config.get("stop_loss_percent", 60))
TG_TOKEN = config.get("telegram_token", "").strip()
TG_CHAT = config.get("telegram_chat_id", "").strip()
PRIVATE_KEY_STR = config.get("private_key", "").strip()
DRY_RUN = bool(config.get("dry_run", True))

BASE_MAX_TRADES_PER_HOUR = int(config.get("max_trades_per_hour", 12))
BASE_MIN_CONFIDENCE_SCORE = float(config.get("min_confidence_score", 70.0))
BASE_MAX_OPEN_POSITIONS = int(config.get("max_open_positions", 8))

SESSION_START_HOUR_UTC = int(config.get("session_start_hour_utc", 0))   # 0–23
SESSION_END_HOUR_UTC = int(config.get("session_end_hour_utc", 23))      # 0–23

LICENSE_FILE = config.get("license_file", "license.ssb")

# These will be tuned by engine profile later
MAX_TRADES_PER_HOUR = BASE_MAX_TRADES_PER_HOUR
MIN_CONFIDENCE_TO_BUY = BASE_MIN_CONFIDENCE_SCORE
MAX_OPEN_POSITIONS = BASE_MAX_OPEN_POSITIONS

client: Optional[AsyncClient] = None

# Track executed trades this hour
trade_timestamps = deque()  # unix timestamps

# License info container (filled at runtime)
LICENSE_INFO: Dict[str, Any] = {
    "ok": False,
    "tier": "DEMO" if DRY_RUN else None,
    "email": "",
    "days_left": None,
    "reason": "Not validated yet",
    "hwid": ""
}

# =========================
#  ENGINE PROFILES
# =========================

@dataclass
class EngineProfile:
    key: str
    label: str
    description: str
    upgrade_reason: str  # Why upgrade to higher tier
    dex_initial_delay: float          # delay before first DexScreener query
    dex_retry_schedule: List[float]   # seconds between subsequent retries
    dex_max_wait: float               # safety cap on total Dex wait
    risk_multiplier: float            # multiply risk.confidence
    min_conf_add: float               # add to MIN_CONFIDENCE base
    max_trades_mult: float            # multiply BASE_MAX_TRADES_PER_HOUR
    max_positions_mult: float         # multiply BASE_MAX_OPEN_POSITIONS
    # ULTRA FEATURES
    trailing_stop_enabled: bool       # PRO+ only
    early_entry_boost: float          # ELITE only - enters X seconds earlier
    priority_fee_mult: float          # Higher = faster tx inclusion
    telegram_full_alerts: bool        # PRO+ only


ENGINE_PROFILES: Dict[str, EngineProfile] = {
    "STANDARD": EngineProfile(
        key="STANDARD",
        label="STD",
        description="Beginner Safety Engine: Safer filters, fewer trades, conservative pace.",
        upgrade_reason="⚡ Upgrade to PRO for LIVE trading, trailing stops, and faster entries!",
        dex_initial_delay=2.0,
        dex_retry_schedule=[2.0, 3.0, 5.0, 8.0],
        dex_max_wait=32.0,
        risk_multiplier=0.95,
        min_conf_add=+5.0,
        max_trades_mult=0.6,
        max_positions_mult=0.6,
        # ULTRA FEATURES - LOCKED
        trailing_stop_enabled=False,
        early_entry_boost=0.0,
        priority_fee_mult=1.0,
        telegram_full_alerts=False,
    ),
    "PRO": EngineProfile(
        key="PRO",
        label="PRO",
        description="Balanced Growth Engine: Full LIVE trading with optimized risk/reward.",
        upgrade_reason="🚀 Upgrade to ELITE for early entries, maximum speed, and aggressive profits!",
        dex_initial_delay=1.5,
        dex_retry_schedule=[2.0, 2.0, 3.0, 4.0],
        dex_max_wait=24.0,
        risk_multiplier=1.0,
        min_conf_add=0.0,
        max_trades_mult=1.0,
        max_positions_mult=1.0,
        # ULTRA FEATURES - UNLOCKED
        trailing_stop_enabled=True,
        early_entry_boost=0.0,
        priority_fee_mult=1.5,
        telegram_full_alerts=True,
    ),
    "ELITE": EngineProfile(
        key="ELITE",
        label="ELITE",
        description="Aggressive Momentum Engine: Fastest entries, early pump detection, maximum profit potential.",
        upgrade_reason="👑 You have the ELITE engine - Maximum power unlocked!",
        dex_initial_delay=1.0,
        dex_retry_schedule=[1.5, 2.0, 3.0, 3.0, 3.0],
        dex_max_wait=20.0,
        risk_multiplier=1.05,
        min_conf_add=-3.0,
        max_trades_mult=1.5,  # FIXED: was 1.4, now 1.5 per spec
        max_positions_mult=1.3,
        # ULTRA FEATURES - FULL UNLOCK
        trailing_stop_enabled=True,
        early_entry_boost=0.5,  # Enters 0.5s earlier than others
        priority_fee_mult=2.0,  # 2x priority fee for fastest tx
        telegram_full_alerts=True,
    ),
    # Reserved turbo profile (INTERNAL ONLY - marketing/demo)
    "TURBO_ELITE": EngineProfile(
        key="TURBO_ELITE",
        label="TURBO ELITE",
        description="INTERNAL ONLY: Ultra-fast sniping for demo/marketing.",
        upgrade_reason="",
        dex_initial_delay=0.7,
        dex_retry_schedule=[1.0, 1.0, 1.5, 2.0, 2.0, 3.0],
        dex_max_wait=18.0,
        risk_multiplier=1.10,
        min_conf_add=-6.0,
        max_trades_mult=1.8,
        max_positions_mult=1.5,
        # ULTRA FEATURES - MAXIMUM
        trailing_stop_enabled=True,
        early_entry_boost=1.0,
        priority_fee_mult=3.0,
        telegram_full_alerts=True,
    ),
}

# Default engine: PRO (will be overridden by selection)
ENGINE: EngineProfile = ENGINE_PROFILES["PRO"]


def select_engine_profile(license_info: Dict[str, Any], dry_run: bool) -> EngineProfile:
    """
    Decide engine based on license tier + DRY_RUN.

    PRO MAX MODE:
    - DRY RUN  → always use ELITE engine (aggressive marketing mode)
    - LIVE:
        STANDARD → STANDARD
        PRO      → PRO
        ELITE    → ELITE
        unknown  → PRO
    """
    tier_raw = (license_info.get("tier") or "").upper()
    tier = tier_raw.replace("STANDARD", "STD")  # normalize

    if dry_run:
        # 🔥 PRO MAX: everyone in DRY RUN feels the ELITE engine.
        chosen = ENGINE_PROFILES["ELITE"]
        logger.info(
            "[ENGINE] PRO MAX mode – DRY RUN using ELITE engine profile "
            "(aggressive, early entries, more action)."
        )
        return chosen

    # LIVE mode: respect paid tiers
    if tier in ("STD", "STANDARD"):
        chosen = ENGINE_PROFILES["STANDARD"]
    elif tier == "PRO":
        chosen = ENGINE_PROFILES["PRO"]
    elif tier == "ELITE":
        chosen = ENGINE_PROFILES["ELITE"]
    else:
        # Unknown tier → fallback to PRO
        chosen = ENGINE_PROFILES["PRO"]

    logger.info(
        "[ENGINE] Loaded profile for plan %s -> %s: %s",
        tier_raw or "UNKNOWN",
        chosen.label,
        chosen.description,
    )
    return chosen


def apply_engine_to_globals(engine: EngineProfile) -> None:
    """
    Tune global parameters according to chosen engine.
    This lets STD/PRO/ELITE really *feel* different while keeping your config
    as the base layer.
    """
    global ENGINE, MIN_CONFIDENCE_TO_BUY, MAX_TRADES_PER_HOUR, MAX_OPEN_POSITIONS

    ENGINE = engine

    # Confidence threshold
    tuned_conf = BASE_MIN_CONFIDENCE_SCORE + ENGINE.min_conf_add
    MIN_CONFIDENCE_TO_BUY = max(0.0, min(100.0, tuned_conf))

    # Trades per hour
    tuned_trades = int(BASE_MAX_TRADES_PER_HOUR * ENGINE.max_trades_mult)
    MAX_TRADES_PER_HOUR = max(1, tuned_trades)

    # Max open positions
    tuned_pos = int(BASE_MAX_OPEN_POSITIONS * ENGINE.max_positions_mult)
    MAX_OPEN_POSITIONS = max(1, tuned_pos)

    logger.info(
        "[ENGINE] Tuned parameters: MIN_CONF=%.1f | MAX_TRADES/h=%d | MAX_POS=%d",
        MIN_CONFIDENCE_TO_BUY,
        MAX_TRADES_PER_HOUR,
        MAX_OPEN_POSITIONS,
    )


# =========================
#  TELEGRAM HELPER
# =========================

def tg(msg: str) -> None:
    """Send Telegram message if token/chat configured."""
    prefix = "[TG-OFF] " if not (TG_TOKEN and TG_CHAT) else ""
    log_msg = f"{prefix}{msg}"
    logger.info(log_msg)

    if not (TG_TOKEN and TG_CHAT):
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": msg},
            timeout=4,
        )
    except Exception:
        # don't crash on TG errors
        pass


# =========================
#  RISK / SCORING MODELS
# =========================

@dataclass
class TokenRisk:
    mint: str
    liquidity_usd: float
    volume_5m: float
    buyers: int
    sellers: int
    fdv: Optional[float] = None
    creator_score: float = 50.0
    bot_density: float = 0.0
    honeypot_flag: bool = False
    confidence: float = 0.0
    reason: str = ""


DEX_API = "https://api.dexscreener.com/latest/dex/tokens/"


def fetch_dex_data(mint: str) -> Optional[Dict[str, Any]]:
    try:
        url = DEX_API + mint
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None
        data = r.json()
        pairs = data.get("pairs") or []
        if not pairs:
            return None
        # choose the highest liquidity pair
        pairs.sort(key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)
        return pairs[0]
    except Exception as e:
        logger.warning(f"[DEX] Error fetching DexScreener for {mint}: {e}")
        return None


async def get_wallet_sol_balance() -> Optional[float]:
    """
    Fetch the wallet's SOL balance for display at startup.
    Returns balance in SOL, or None on error.
    """
    if not PRIVATE_KEY_STR:
        return None
    try:
        try:
            keypair = Keypair.from_base58_string(PRIVATE_KEY_STR)
        except Exception:
            keypair = Keypair.from_bytes(base58.b58decode(PRIVATE_KEY_STR))
        
        global client
        if client is None:
            client = AsyncClient(RPC or "https://api.mainnet-beta.solana.com")
        
        resp = await client.get_balance(keypair.pubkey())
        if resp.value is not None:
            return resp.value / 1_000_000_000  # lamports to SOL
        return None
    except Exception as e:
        logger.warning(f"[WALLET] Failed to fetch balance: {e}")
        return None


async def check_freeze_authority(mint: str) -> bool:
    """
    Check if mint has Freeze Authority enabled.
    Returns TRUE if potentially dangerous (freeze auth exists).
    """
    global client
    try:
        if client is None:
            client = AsyncClient(RPC or "https://api.mainnet-beta.solana.com")
        
        # We need to fetch the Mint Account info
        # Using jsonParsed to make it easy
        resp = await client.get_account_info_json_parsed(Pubkey.from_string(mint))
        if not resp.value:
            return False # Can't find account, assume safe or just ignore
            
        data = resp.value.data
        # data should be ParsedAccount(program='spl-token', parsed=..., space=...)
        # We access the parsed dict
        # structure: data.parsed['info']['freezeAuthority']
        
        # In newer solders/solana versions, checking structure carefully:
        # It might be an object, need to access attributes or dict.
        # Safest way with 'jsonParsed' encoding is usually a dictionary traversal.
        
        # Assuming standard response structure for SPL Token:
        # freezeAuthority is None if disabled.
        # It is a Pubkey string if enabled.
        
        # Note: 'solana' lib 0.32+ usually returns objects. 
        # let's try getattr first, then dict access.
        
        # Simpler approach: check raw bytes if we wanted, but json is nicer.
        # Let's assume we can access .parsed (if object) or ['parsed'] (if dict)
        
        # For safety against library version diffs, let's wrap in try/except generic
        parsed = None
        if hasattr(data, "parsed"):
            parsed = data.parsed
        elif isinstance(data, dict):
             parsed = data.get("parsed")
             
        if parsed:
            info = parsed.get("info", {})
            f_auth = info.get("freezeAuthority")
            if f_auth:
                logger.warning(f"[RUG-CHECK] ⚠️ Freeze Authority DETECTED for {mint[:6]}! (Auth: {f_auth})")
                return True
                
        return False
        
    except Exception as e:
        logger.warning(f"[RUG-CHECK] Failed to check freeze auth for {mint}: {e}")
        return False # Fail open (allow trade) or closed? Fail open to avoid blocking legit trades on RPC error.


def local_honeypot_heuristic(pair: Dict[str, Any]) -> bool:
    """Very basic heuristics based on Dex data (not 100% safe)."""
    try:
        txns = pair.get("txns", {})
        m5 = txns.get("m5", {})
        buys = m5.get("buys", 0)
        sells = m5.get("sells", 0)

        # no sells but many buys in 5m → suspicious
        if buys >= 20 and sells == 0:
            return True

        # extremely unbalanced liquidity vs volume
        liq = float(pair.get("liquidity", {}).get("usd", 0))
        vol5m = float(pair.get("volume", {}).get("m5", 0))
        if liq < 2000 and vol5m > liq * 5:
            return True
    except Exception:
        pass
    return False


def estimate_bot_density(pair: Dict[str, Any]) -> float:
    """Estimate bot density from txns – rough proxy."""
    try:
        txns = pair.get("txns", {})
        m5 = txns.get("m5", {})
        buys = float(m5.get("buys", 0))
        sells = float(m5.get("sells", 0))
        total = buys + sells
        if total == 0:
            return 0.0
        # naive: if buys >> sells, treat as more 'botty'
        ratio = buys / max(sells, 1.0)
        density = min(100.0, max(0.0, (ratio - 1.0) * 10.0))
        return density
    except Exception:
        return 0.0


def estimate_creator_score(pair: Dict[str, Any]) -> float:
    """
    Placeholder – DexScreener doesn't expose deployer history directly,
    but we can bump score for decent liquidity & volume.
    """
    try:
        liq = float(pair.get("liquidity", {}).get("usd", 0))
        vol_24h = float(pair.get("volume", {}).get("h24", 0))

        score = 40.0
        if liq > 20_000:
            score += 20
        elif liq > 10_000:
            score += 10

        if vol_24h > 200_000:
            score += 20
        elif vol_24h > 50_000:
            score += 10

        return max(0.0, min(100.0, score))
    except Exception:
        return 50.0


def build_risk_model(mint: str) -> Optional[TokenRisk]:
    pair = fetch_dex_data(mint)
    if not pair:
        logger.info(f"[DEX] No pairs found for {mint}")
        return None

    liq = float(pair.get("liquidity", {}).get("usd", 0))
    vol5m = float(pair.get("volume", {}).get("m5", 0))
    fdv = pair.get("fdv")

    txns = pair.get("txns", {})
    m5 = txns.get("m5", {})
    buyers = int(m5.get("buys", 0))
    sellers = int(m5.get("sells", 0))

    creator_score = estimate_creator_score(pair)
    bot_density = estimate_bot_density(pair)
    hp_flag = local_honeypot_heuristic(pair)

    # Base confidence score (before engine multiplier)
    confidence = 0.0

    # Liquidity
    if liq >= MIN_LIQUIDITY:
        confidence += 25
    elif liq >= MIN_LIQUIDITY * 0.7:
        confidence += 10
    else:
        confidence -= 20

    # Volume 5m
    if vol5m >= MIN_VOLUME_5M:
        confidence += 25
    elif vol5m >= MIN_VOLUME_5M * 0.7:
        confidence += 10
    else:
        confidence -= 15

    # Creator
    confidence += (creator_score - 50) * 0.3  # normalize around 50

    # Bots
    if bot_density > 80:
        confidence -= 30
    elif bot_density > 50:
        confidence -= 15

    # Honeypot-like behavior
    if hp_flag:
        confidence -= 40

    # Apply engine-level risk multiplier
    confidence *= ENGINE.risk_multiplier

    confidence = max(0.0, min(100.0, confidence))

    reason_parts = []
    reason_parts.append(f"Liq ${liq:,.0f}")
    reason_parts.append(f"Vol5m ${vol5m:,.0f}")
    reason_parts.append(f"Buys/Sells 5m: {buyers}/{sellers}")
    reason_parts.append(f"CreatorScore {creator_score:.1f}")
    reason_parts.append(f"BotDensity {bot_density:.1f}%")
    if hp_flag:
        reason_parts.append("HoneypotHeuristic=TRUE")
    reason_parts.append(f"EngineRiskMult x{ENGINE.risk_multiplier:.2f}")

    reason = " | ".join(reason_parts)

    return TokenRisk(
        mint=mint,
        liquidity_usd=liq,
        volume_5m=vol5m,
        buyers=buyers,
        sellers=sellers,
        fdv=fdv,
        creator_score=creator_score,
        bot_density=bot_density,
        honeypot_flag=hp_flag,
        confidence=confidence,
        reason=reason,
    )


def risk_passes(risk: TokenRisk) -> bool:
    if risk.liquidity_usd < MIN_LIQUIDITY:
        logger.info(
            f"[FILTER] Low liquidity – Skipped {risk.mint[:6]} | "
            f"Liq ${risk.liquidity_usd:,.0f}"
        )
        return False

    if risk.volume_5m < MIN_VOLUME_5M:
        logger.info(
            f"[FILTER] Low 5m volume – Skipped {risk.mint[:6]} | "
            f"Vol5m ${risk.volume_5m:,.0f}"
        )
        return False

    if risk.honeypot_flag:
        logger.info(
            f"[FILTER] Honeypot heuristic triggered – Skipped {risk.mint[:6]}"
        )
        return False

    if risk.bot_density > 85:
        logger.info(
            f"[FILTER] High bot density ({risk.bot_density:.1f}%) – Skipped {risk.mint[:6]}"
        )
        return False

    if risk.confidence < MIN_CONFIDENCE_TO_BUY:
        logger.info(
            f"[FILTER] Confidence {risk.confidence:.1f} < {MIN_CONFIDENCE_TO_BUY:.1f} – "
            f"Skipped {risk.mint[:6]}"
        )
        return False

    return True


# =========================
#  STATS & POSITIONS
# =========================

@dataclass
class SessionStats:
    tokens_seen: int = 0
    tokens_with_dex_data: int = 0
    tokens_passed_filters: int = 0
    dry_run_buys: int = 0
    live_buys: int = 0
    simulated_exits_tp: int = 0
    simulated_exits_sl: int = 0


stats = SessionStats()

# positions[mint] = {
#   "entry_price": float,
#   "amount": float,
#   "created_at": timestamp
# }
positions: Dict[str, Dict[str, Any]] = {}

LAST_STATS_PRINT = time.time()


def can_trade_now() -> bool:
    now = time.time()
    # remove timestamps older than 1h
    while trade_timestamps and now - trade_timestamps[0] > 3600:
        trade_timestamps.popleft()
    return len(trade_timestamps) < MAX_TRADES_PER_HOUR


def register_trade() -> None:
    trade_timestamps.append(time.time())


def in_trading_session() -> bool:
    if SESSION_START_HOUR_UTC == SESSION_END_HOUR_UTC:
        return True  # full day
    now_utc_hour = int(time.gmtime().tm_hour)
    if SESSION_START_HOUR_UTC < SESSION_END_HOUR_UTC:
        return SESSION_START_HOUR_UTC <= now_utc_hour < SESSION_END_HOUR_UTC
    else:
        # wrap over midnight
        return (
            now_utc_hour >= SESSION_START_HOUR_UTC
            or now_utc_hour < SESSION_END_HOUR_UTC
        )


def get_price(mint: str) -> Optional[float]:
    try:
        url = f"https://price.jup.ag/v1/price?id={mint}"
        r = requests.get(url, timeout=5)
        data = r.json()
        return float(data["data"]["price"])
    except Exception as e:
        logger.warning(f"[PRICE] Failed to fetch price for {mint}: {e}")
        return None


async def register_position(mint: str) -> None:
    if len(positions) >= MAX_OPEN_POSITIONS:
        logger.info(
            f"[POS] Max open positions reached ({MAX_OPEN_POSITIONS}) – "
            f"not tracking {mint[:6]}."
        )
        return

    price = get_price(mint)
    if price is None:
        logger.info(f"[POS] No entry price for {mint[:6]} – not tracking position.")
        return

    positions[mint] = {
        "entry_price": price,
        "amount": BUY_AMOUNT,
        "created_at": time.time(),
    }
    logger.info(
        f"[POS] Tracking position {mint[:6]} | entry {price:.8f} | amount {BUY_AMOUNT} SOL"
    )


async def execute_sell(mint: str, reason: str, price: float) -> None:
    """
    Exit logic – DRY RUN is fully simulated.
    LIVE mode uses Jupiter v6 API to swap Token -> SOL.
    """
    pos = positions.get(mint)
    if not pos:
        return

    entry = pos["entry_price"]
    multiple = price / entry if entry > 0 else 1.0

    if DRY_RUN:
        logger.info(
            f"[DRY-RUN SELL] {mint[:6]} | reason={reason} | entry={entry:.8f} | "
            f"price={price:.8f} | x{multiple:.2f}"
        )
        tg(
            f"🟡 DRY-RUN SELL {mint[:6]} ({reason})\n"
            f"Entry: {entry:.8f}\nNow: {price:.8f} (x{multiple:.2f})"
        )
        # remove position
        positions.pop(mint, None)
        return

    # LIVE mode – Jupiter Swap
    logger.info(f"[SELL] Attempting LIVE SELL for {mint[:6]} via Jupiter...")
    
    if not PRIVATE_KEY_STR:
        logger.error("[SELL] No private key configured! Cannot sell.")
        tg(f"🔴 SELL FAILED {mint[:6]}: No Private Key")
        return

    # RETRY LOOP FOR ROBUSTNESS
    max_retries = 5
    current_slippage_bps = 200 # start 2%
    
    for attempt in range(1, max_retries + 1):
        try:
            # Load Keypair
            try:
                keypair = Keypair.from_base58_string(PRIVATE_KEY_STR)
            except Exception:
                keypair = Keypair.from_bytes(base58.b58decode(PRIVATE_KEY_STR))

            logger.info(f"[SELL] Attempt {attempt}/{max_retries} | Slippage {current_slippage_bps/100}%")

            # 1. Get Quote (Token -> SOL)
            user_wallet = str(keypair.pubkey())
            global client
            if client is None:
                client = AsyncClient(RPC or "https://api.mainnet-beta.solana.com")
            
            logger.warning("[SELL] Live sell logic needs Token Balance check. Implementing 'Blind' sell based on estimated amount.")
            estimated_tokens = (pos["amount"] / pos["entry_price"])
            amount_lamports = int(estimated_tokens * 1_000_000) # 6 decimals assumption
            
            quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={mint}&outputMint=So11111111111111111111111111111111111111112&amount={amount_lamports}&slippageBps={current_slippage_bps}"
            
            q = requests.get(quote_url, timeout=5)
            if q.status_code != 200:
                raise Exception(f"Quote failed: {q.text}")
            quote_data = q.json()
            
            # 2. Get Swap Transaction (priority fee scales by plan)
            base_priority_fee = 100000  # 0.0001 SOL base
            priority_fee = int(base_priority_fee * ENGINE.priority_fee_mult)
            swap_payload = {
                "quoteResponse": quote_data,
                "userPublicKey": user_wallet,
                "wrapAndUnwrapSol": True,
                "prioritizationFeeLamports": priority_fee  # Scales by plan tier
            }
            s = requests.post("https://quote-api.jup.ag/v6/swap", json=swap_payload, timeout=10)
            if s.status_code != 200:
                raise Exception(f"Swap build failed: {s.text}")
            
            swap_data = s.json()
            encoded_tx = swap_data["swapTransaction"]
            
            # 3. Sign and Send
            raw_tx = base58.b58decode(encoded_tx)
            tx = VersionedTransaction.from_bytes(raw_tx)
            
            blockhash = tx.message.recent_blockhash
            signature = keypair.sign_message(bytes(tx.message))
            signed_tx = VersionedTransaction.populate(tx.message, [signature])
            
            encoded_signed = base58.b58encode(bytes(signed_tx)).decode()
            
            txid = "RPC_NOT_CONFIGURED"
            if RPC:
                 rpc_payload = {
                     "jsonrpc": "2.0",
                     "id": 1,
                     "method": "sendTransaction",
                     "params": [encoded_signed, {"encoding": "base58", "skipPreflight": True}]
                 }
                 rpc_req = requests.post(RPC, json=rpc_payload, timeout=5)
                 rpc_res = rpc_req.json()
                 if "error" in rpc_res:
                     raise Exception(f"RPC Error: {rpc_res['error']}")
                 txid = rpc_res.get("result")
            else:
                logger.error("RPC not configured, cannot send tx.")
                break # fatal

            logger.info(f"[SELL] LIVE SELL SENT! Tx: {txid}")
            tg(
                f"🟠 LIVE SELL {mint[:6]}\n"
                f"Entry: {entry:.8f}\nNow: {price:.8f}\nTx: {txid}"
            )
            
            positions.pop(mint, None)
            return # Success!

        except Exception as e:
            logger.error(f"[SELL] Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                tg(f"🔴 SELL ERROR {mint[:6]} (Final): {e}")
            else:
                # Ramp up slippage for next retry
                current_slippage_bps += 100 # +1%
                await asyncio.sleep(1.0) # wait 1s


async def monitor_positions() -> None:
    global LAST_STATS_PRINT
    while True:
        await asyncio.sleep(8)

        # Position monitoring for TP/SL
        if positions:
            for mint, pos in list(positions.items()):
                price = get_price(mint)
                if price is None:
                    continue
                entry = pos["entry_price"]

                # TP
                if price >= entry * (1 + TP / 100.0):
                    stats.simulated_exits_tp += 1
                    await execute_sell(mint, "TP", price)
                    continue

                # SL
                if price <= entry * (1 - SL / 100.0):
                    stats.simulated_exits_sl += 1
                    await execute_sell(mint, "SL", price)
                    continue

        # Periodic stats print every ~60s
        now = time.time()
        if now - LAST_STATS_PRINT > 60:
            LAST_STATS_PRINT = now
            logger.info(
                "[STATS] Seen=%d | DexOK=%d | Passed=%d | DRY_BUYS=%d | LIVE_BUYS=%d | "
                "TP_Exits=%d | SL_Exits=%d | OpenPos=%d",
                stats.tokens_seen,
                stats.tokens_with_dex_data,
                stats.tokens_passed_filters,
                stats.dry_run_buys,
                stats.live_buys,
                stats.simulated_exits_tp,
                stats.simulated_exits_sl,
                len(positions),
            )


# =========================
#  BUY EXECUTION
# =========================

async def execute_buy(mint: str, risk: TokenRisk) -> Optional[str]:
    """
    Execute buy on Pump.fun via pumpportal API.
    In DRY_RUN this only logs.
    """
    if not in_trading_session():
        logger.info(
            f"[SESSION] Outside trading window (%02d–%02d UTC) – not buying %s",
            SESSION_START_HOUR_UTC,
            SESSION_END_HOUR_UTC,
            mint[:6],
        )
        return None

    if not can_trade_now():
        logger.info(f"[LIMIT] Max trades/hour reached – not buying {mint[:6]}")
        return None

    if DRY_RUN:
        logger.info(
            f"[DRY-RUN BUY] {mint[:6]} | Amount: {BUY_AMOUNT} SOL | "
            f"Conf {risk.confidence:.1f} | {risk.reason}"
        )
        tg(
            f"🟡 DRY RUN BUY {mint[:6]} | {BUY_AMOUNT} SOL\n"
            f"Conf {risk.confidence:.1f}\n{risk.reason}"
        )
        stats.dry_run_buys += 1
        register_trade()
        await register_position(mint)
        return "DRY_RUN_TXID"

    # LIVE mode – real buy hook via Pump.fun API
    try:
        payload = {
            "action": "buy",
            "mint": mint,
            "amount": BUY_AMOUNT,
            "slippage": 15,
            "priorityFee": 0.001,
            "privateKey": PRIVATE_KEY_STR,  # Requires private key for pump portal trade
        }
        r = requests.post(
            "https://pumpportal.fun/api/trade", json=payload, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        txid = data.get("txid") or data.get("signature")
        logger.info(f"[BUY] LIVE BUY {mint[:6]} @ {BUY_AMOUNT} SOL | txid={txid}")
        tg(
            f"🟢 LIVE BUY {mint[:6]} | {BUY_AMOUNT} SOL\n"
            f"Conf {risk.confidence:.1f}\n{risk.reason}\nTx: {txid}"
        )
        stats.live_buys += 1
        register_trade()
        await register_position(mint)
        return txid
    except Exception as e:
        logger.error(f"[BUY] Error executing LIVE buy for {mint}: {e}")
        tg(f"❌ BUY ERROR {mint[:6]}: {e}")
        return None


# =========================
#  PUMPFUN STREAM HANDLER
# =========================

PUMP_WS = "wss://pumpportal.fun/api/data"


async def get_risk_with_retries(mint: str) -> Optional[TokenRisk]:
    """
    Centralized DexScreener retry logic, tuned by ENGINE profile.
    Handles indexing delay after token creation.
    """
    total_wait = 0.0

    # Initial wait (reduced by early_entry_boost for higher tiers)
    effective_delay = max(0.3, ENGINE.dex_initial_delay - ENGINE.early_entry_boost)
    if effective_delay > 0:
        await asyncio.sleep(effective_delay)
        total_wait += effective_delay
        
    # Log early entry advantage for ELITE
    if ENGINE.early_entry_boost > 0:
        logger.debug(f"[EARLY ENTRY] ⚡ Entered {ENGINE.early_entry_boost:.1f}s earlier (ELITE advantage)")

    risk = build_risk_model(mint)
    if risk:
        # ASYNC FREEZE AUTH CHECK
        is_frozen = await check_freeze_authority(mint)
        if is_frozen:
             logger.warning(f"[RISK] {mint[:6]} Rejected: Freeze Authority Enabled")
             risk.confidence = 0 # Nuke confidence
             risk.reason += " | FREEZE_AUTH_DETECTED"
             
        return risk

    # Retry schedule
    for delay in ENGINE.dex_retry_schedule:
        if total_wait + delay > ENGINE.dex_max_wait:
            break
        await asyncio.sleep(delay)
        total_wait += delay
        risk = build_risk_model(mint)
        if risk:
            # ASYNC FREEZE AUTH CHECK (Retry loop)
            is_frozen = await check_freeze_authority(mint)
            if is_frozen:
                 logger.warning(f"[RISK] {mint[:6]} Rejected: Freeze Authority Enabled")
                 risk.confidence = 0
                 risk.reason += " | FREEZE_AUTH_DETECTED"
            return risk

    logger.info(
        "[DEX] No data for %s even after %.1fs total wait – skipping.",
        mint[:6],
        total_wait,
    )
    return None


async def pumpfun_listener():
    """
    Subscribe to new Pump.fun tokens and evaluate them.
    """
    global client
    if client is None and RPC:
        client = AsyncClient(RPC)

    while True:
        try:
            logger.info(f"[WS] Connecting to {PUMP_WS} ...")
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                logger.info("[WS] Subscribed to Pump.fun new tokens.")
                tg("⚡ Connected to Pump.fun stream (Sol Sniper Bot PRO).")

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        mint = msg.get("mint")
                        if not mint:
                            continue

                        stats.tokens_seen += 1

                        logger.info("\n🚀 NEW TOKEN: %s", mint)
                        tg(f"🚀 NEW PUMPFUN TOKEN: {mint}")

                        # DexScreener indexing & risk model via engine-aware retry logic
                        risk = await get_risk_with_retries(mint)
                        if risk:
                            stats.tokens_with_dex_data += 1
                        else:
                            continue

                        logger.info(
                            "[RISK] %s | Conf %.1f | %s",
                            mint[:6],
                            risk.confidence,
                            risk.reason,
                        )
                        tg(
                            f"📊 RISK {mint[:6]} | Conf {risk.confidence:.1f}\n"
                            f"{risk.reason}"
                        )

                        if not risk_passes(risk):
                            continue

                        stats.tokens_passed_filters += 1

                        # Execute buy (or dry-run buy)
                        await execute_buy(mint, risk)

                    except Exception as inner_e:
                        logger.error(f"[WS] Error processing message: {inner_e}")

        except Exception as e:
            logger.error(f"[WS] Error: {e}")
            tg(f"⚠️ Pump.fun WS error – reconnecting in 3s...\n{e}")
            await asyncio.sleep(3)


# =========================
#  MAIN ENTRY
# =========================

async def main():
    global LICENSE_INFO

    mode = "DRY RUN" if DRY_RUN else "LIVE"

    # ----- LICENSE CHECK (file-based) -----
    LICENSE_INFO = validate_license(
        license_path=LICENSE_FILE,
        require_pro=not DRY_RUN,
        dry_run=DRY_RUN,
    )

    if not DRY_RUN and not LICENSE_INFO["ok"]:
        logger.error("❌ License validation failed: %s", LICENSE_INFO["reason"])
        tg(f"❌ LICENSE ERROR – {LICENSE_INFO['reason']}")
        return

    if DRY_RUN and not LICENSE_INFO["ok"]:
        logger.info("🟡 Running in DRY RUN without valid license: %s", LICENSE_INFO["reason"])

    # ----- ENGINE SELECTION & TUNING -----
    engine = select_engine_profile(LICENSE_INFO, DRY_RUN)
    apply_engine_to_globals(engine)

    logger.info(
        "Sol Sniper Bot PRO – Mode: %s | RPC: %s | Buy: %.2f SOL | TP: %.1f%% | SL: %.1f%% | "
        "Filters: Min Liq $%s, Vol 5m $%s | Limits: Max %d trades / hour | Min Conf: %.1f | "
        "MaxOpenPos=%d | SessionUTC=%02d-%02d",
        mode,
        RPC or "N/A",
        BUY_AMOUNT,
        TP,
        SL,
        f"{MIN_LIQUIDITY:,.0f}",
        f"{MIN_VOLUME_5M:,.0f}",
        MAX_TRADES_PER_HOUR,
        MIN_CONFIDENCE_TO_BUY,
        MAX_OPEN_POSITIONS,
        SESSION_START_HOUR_UTC,
        SESSION_END_HOUR_UTC,
    )

    logger.info(
        "License: tier=%s | email=%s | days_left=%s | reason=%s",
        LICENSE_INFO.get("tier"),
        LICENSE_INFO.get("email"),
        LICENSE_INFO.get("days_left"),
        LICENSE_INFO.get("reason"),
    )

    logger.info(
        "Engine: %s – %s (risk_mult=%.2f, dex_initial=%.1fs, dex_max_wait=%.1fs)",
        ENGINE.label,
        ENGINE.description,
        ENGINE.risk_multiplier,
        ENGINE.dex_initial_delay,
        ENGINE.dex_max_wait,
    )

    # ULTRA FEATURES STATUS
    logger.info(
        "Ultra Features: TrailingStop=%s | EarlyEntry=%.1fs | PriorityFee=%.1fx | FullAlerts=%s",
        "✅" if ENGINE.trailing_stop_enabled else "❌ LOCKED",
        ENGINE.early_entry_boost,
        ENGINE.priority_fee_mult,
        "✅" if ENGINE.telegram_full_alerts else "❌ LOCKED",
    )
    
    # UPGRADE PROMPT (if not ELITE)
    if ENGINE.upgrade_reason and ENGINE.key != "ELITE":
        logger.info("💡 %s", ENGINE.upgrade_reason)
        tg(f"💡 {ENGINE.upgrade_reason}")

    tg(
        f"Sol Sniper Bot PRO\n"
        f"Mode: {mode}\n"
        f"RPC: {RPC or 'N/A'}\n"
        f"Buy: {BUY_AMOUNT} SOL | TP: {TP}% | SL: {SL}%\n"
        f"Filters: Min Liq ${MIN_LIQUIDITY:,.0f}, Vol 5m ${MIN_VOLUME_5M:,.0f}\n"
        f"Limits: Max {MAX_TRADES_PER_HOUR} trades/hour | "
        f"Min Conf: {MIN_CONFIDENCE_TO_BUY}\n"
        f"Max Open Positions: {MAX_OPEN_POSITIONS}\n"
        f"Session (UTC): {SESSION_START_HOUR_UTC:02d}-{SESSION_END_HOUR_UTC:02d}\n"
        f"License: {LICENSE_INFO.get('tier')} | {LICENSE_INFO.get('email')} | "
        f"Days left: {LICENSE_INFO.get('days_left')}\n"
        f"Engine: {ENGINE.label}: {ENGINE.description}"
    )

    # Start background position monitor
    asyncio.create_task(monitor_positions())

    # Show wallet balance if LIVE mode
    if not DRY_RUN and PRIVATE_KEY_STR:
        balance = await get_wallet_sol_balance()
        if balance is not None:
            logger.info(f"💰 Wallet Balance: {balance:.4f} SOL")
            tg(f"💰 Wallet Balance: {balance:.4f} SOL")
        else:
            logger.warning("[WALLET] Could not fetch wallet balance.")

    await pumpfun_listener()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user (Ctrl+C).")
