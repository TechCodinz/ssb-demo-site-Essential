"""
Sol Sniper Bot PRO - Divine Features Module
🌟 The ultimate collection of mind-blowing trading enhancements
Built with divine love for maximum user success
"""
import asyncio
import math
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
import hashlib
import json


# ============================================================
# 🧠 AI SENTIMENT ENGINE
# Real-time social sentiment analysis
# ============================================================

class SentimentLevel(Enum):
    EXTREME_FEAR = -2
    FEAR = -1
    NEUTRAL = 0
    GREED = 1
    EXTREME_GREED = 2


@dataclass
class SentimentSignal:
    """Social sentiment signal"""
    source: str  # twitter, telegram, reddit
    score: float  # -1 to 1
    volume: int  # number of mentions
    velocity: float  # change rate
    keywords: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AISentimentEngine:
    """
    🧠 AI-Powered Sentiment Analysis
    
    Aggregates social signals from multiple sources to gauge
    market sentiment and predict momentum shifts.
    """
    
    # Bullish/bearish keyword weights
    BULLISH_KEYWORDS = {
        "moon": 0.8, "pump": 0.7, "gem": 0.6, "bullish": 0.9,
        "ape": 0.5, "buy": 0.4, "hodl": 0.6, "diamond": 0.7,
        "rocket": 0.8, "100x": 0.9, "alpha": 0.7, "early": 0.6
    }
    
    BEARISH_KEYWORDS = {
        "dump": -0.8, "rug": -0.9, "scam": -1.0, "sell": -0.5,
        "bearish": -0.7, "red": -0.4, "crash": -0.8, "dead": -0.9,
        "honeypot": -1.0, "avoid": -0.7, "fake": -0.8
    }
    
    def __init__(self):
        self.sentiment_cache: Dict[str, SentimentSignal] = {}
        self.global_sentiment = SentimentLevel.NEUTRAL
        self.fear_greed_index = 50  # 0-100 scale
        
    async def analyze_token_sentiment(self, mint: str, social_data: dict) -> Tuple[float, SentimentLevel]:
        """
        Analyze sentiment for a specific token.
        Returns: (sentiment_score, sentiment_level)
        """
        text_data = social_data.get("mentions", [])
        
        # Calculate keyword scores
        bullish_score = 0
        bearish_score = 0
        
        for text in text_data:
            text_lower = text.lower()
            for keyword, weight in self.BULLISH_KEYWORDS.items():
                if keyword in text_lower:
                    bullish_score += weight
            for keyword, weight in self.BEARISH_KEYWORDS.items():
                if keyword in text_lower:
                    bearish_score += weight
                    
        # Normalize
        total = abs(bullish_score) + abs(bearish_score) + 0.1
        sentiment_score = (bullish_score + bearish_score) / total
        
        # Determine level
        if sentiment_score >= 0.6:
            level = SentimentLevel.EXTREME_GREED
        elif sentiment_score >= 0.2:
            level = SentimentLevel.GREED
        elif sentiment_score <= -0.6:
            level = SentimentLevel.EXTREME_FEAR
        elif sentiment_score <= -0.2:
            level = SentimentLevel.FEAR
        else:
            level = SentimentLevel.NEUTRAL
            
        # Cache result
        self.sentiment_cache[mint] = SentimentSignal(
            source="aggregated",
            score=sentiment_score,
            volume=len(text_data),
            velocity=social_data.get("velocity", 0),
            keywords=list(self.BULLISH_KEYWORDS.keys())[:5]
        )
        
        return sentiment_score, level

    def get_fear_greed_index(self) -> int:
        """
        Calculate the Fear & Greed Index (0-100)
        0 = Extreme Fear, 100 = Extreme Greed
        """
        if not self.sentiment_cache:
            return 50
            
        avg_score = sum(s.score for s in self.sentiment_cache.values()) / len(self.sentiment_cache)
        # Convert -1 to 1 scale to 0-100
        self.fear_greed_index = int((avg_score + 1) * 50)
        return self.fear_greed_index


# ============================================================
# ⚡ MOMENTUM CASCADE DETECTION
# Detects when multiple signals align for explosive moves
# ============================================================

@dataclass
class CascadeEvent:
    """A momentum cascade event"""
    mint: str
    signals_aligned: int
    cascade_strength: float  # 0-1
    trigger_time: datetime
    expected_move: float  # % expected price move
    signals: List[str]


class MomentumCascadeDetector:
    """
    ⚡ Momentum Cascade Detection
    
    Identifies when multiple independent signals align,
    creating a "cascade" effect for explosive price moves.
    
    When 5+ signals align simultaneously, the probability
    of a significant price move increases dramatically.
    """
    
    SIGNAL_TYPES = [
        "volume_spike",      # 3x volume in 5 min
        "whale_buy",         # Large wallet accumulation  
        "holder_surge",      # New holder spike
        "social_explosion",  # Viral social activity
        "liquidity_add",     # LP added
        "momentum_break",    # Price breaks resistance
        "bot_detection",     # Other bots entering
        "pattern_match",     # Chart pattern confirmed
    ]
    
    def __init__(self):
        self.active_cascades: Dict[str, CascadeEvent] = {}
        self.cascade_history: List[CascadeEvent] = []
        
    async def check_cascade(self, mint: str, signals: Dict[str, bool]) -> Optional[CascadeEvent]:
        """
        Check if enough signals align for a cascade.
        Returns cascade event if detected.
        """
        aligned_signals = [s for s, active in signals.items() if active]
        count = len(aligned_signals)
        
        if count < 4:
            return None
            
        # Calculate cascade strength
        strength = count / len(self.SIGNAL_TYPES)
        
        # Calculate expected move based on strength
        expected_move = strength * 100  # Up to 100% for perfect alignment
        
        cascade = CascadeEvent(
            mint=mint,
            signals_aligned=count,
            cascade_strength=strength,
            trigger_time=datetime.utcnow(),
            expected_move=expected_move,
            signals=aligned_signals
        )
        
        self.active_cascades[mint] = cascade
        self.cascade_history.append(cascade)
        
        return cascade
    
    def get_cascade_alert(self, cascade: CascadeEvent) -> str:
        """Generate alert message for cascade event"""
        emoji = "🌟" if cascade.signals_aligned >= 6 else "⚡"
        
        return (
            f"{emoji} MOMENTUM CASCADE DETECTED!\n"
            f"Token: {cascade.mint[:12]}...\n"
            f"Signals Aligned: {cascade.signals_aligned}/8\n"
            f"Cascade Strength: {cascade.cascade_strength*100:.0f}%\n"
            f"Expected Move: +{cascade.expected_move:.0f}%\n"
            f"Triggers: {', '.join(cascade.signals[:3])}"
        )


# ============================================================
# 🐋 SMART MONEY TRACKER
# Follow the whales and smart wallets
# ============================================================

@dataclass 
class WhaleWallet:
    """A tracked whale wallet"""
    address: str
    nickname: str
    win_rate: float
    avg_return: float
    total_trades: int
    last_trade: datetime
    following: bool = False


@dataclass
class WhaleMove:
    """A whale's trading action"""
    wallet: WhaleWallet
    action: str  # BUY, SELL
    mint: str
    amount_sol: float
    timestamp: datetime


class SmartMoneyTracker:
    """
    🐋 Smart Money Tracking System
    
    Tracks known profitable wallets ("whales") and
    alerts when they make moves. Copy their trades
    for higher win rates.
    """
    
    def __init__(self):
        # Known profitable wallets (would be populated from on-chain analysis)
        self.tracked_wallets: Dict[str, WhaleWallet] = {}
        self.recent_moves: List[WhaleMove] = []
        self.whale_holdings: Dict[str, Set[str]] = {}  # wallet -> mints
        
    async def track_wallet(self, address: str, nickname: str = ""):
        """Add a wallet to tracking"""
        self.tracked_wallets[address] = WhaleWallet(
            address=address,
            nickname=nickname or f"Whale-{address[:6]}",
            win_rate=0.0,
            avg_return=0.0,
            total_trades=0,
            last_trade=datetime.utcnow(),
            following=True
        )
        
    async def detect_whale_activity(self, mint: str, transactions: List[dict]) -> List[WhaleMove]:
        """
        Check transactions for whale activity.
        Returns list of whale moves detected.
        """
        whale_moves = []
        
        for tx in transactions:
            wallet = tx.get("wallet", "")
            if wallet in self.tracked_wallets:
                whale = self.tracked_wallets[wallet]
                
                move = WhaleMove(
                    wallet=whale,
                    action="BUY" if tx.get("side") == "buy" else "SELL",
                    mint=mint,
                    amount_sol=tx.get("amount_sol", 0),
                    timestamp=datetime.utcnow()
                )
                
                whale_moves.append(move)
                self.recent_moves.append(move)
                
                # Update whale holdings
                if move.action == "BUY":
                    if wallet not in self.whale_holdings:
                        self.whale_holdings[wallet] = set()
                    self.whale_holdings[wallet].add(mint)
                    
        return whale_moves
    
    def is_whale_holding(self, mint: str) -> bool:
        """Check if any tracked whale is holding this token"""
        for holdings in self.whale_holdings.values():
            if mint in holdings:
                return True
        return False
    
    def get_whale_confidence_boost(self, mint: str) -> float:
        """
        Get confidence boost from whale activity.
        If whales are buying, boost confidence.
        """
        whale_count = sum(
            1 for holdings in self.whale_holdings.values()
            if mint in holdings
        )
        
        # Up to 15% boost for massive whale interest
        return min(whale_count * 3, 15)


# ============================================================
# 🏆 GAMIFICATION & ACHIEVEMENTS
# Make trading fun and rewarding
# ============================================================

class AchievementType(Enum):
    FIRST_BLOOD = "first_blood"
    PROFIT_STREAK = "profit_streak"
    DIAMOND_HANDS = "diamond_hands"
    WHALE_HUNTER = "whale_hunter"
    NIGHT_OWL = "night_owl"
    EARLY_BIRD = "early_bird"
    LEGENDARY_FINDER = "legendary_finder"
    HUNDRED_TRADES = "hundred_trades"
    THOUSAND_SOL = "thousand_sol"
    PERFECT_WEEK = "perfect_week"


@dataclass
class Achievement:
    """An unlockable achievement"""
    type: AchievementType
    name: str
    description: str
    emoji: str
    xp_reward: int
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None


@dataclass
class UserProgress:
    """User's gamification progress"""
    user_id: str
    level: int = 1
    xp: int = 0
    total_trades: int = 0
    win_streak: int = 0
    best_streak: int = 0
    total_profit_sol: float = 0.0
    achievements: List[Achievement] = field(default_factory=list)
    rank_title: str = "Rookie Sniper"


class GamificationEngine:
    """
    🏆 Gamification System
    
    Makes trading fun with XP, levels, achievements,
    and leaderboards. Users get hooked on progressing!
    """
    
    RANK_TITLES = {
        1: "Rookie Sniper",
        5: "Junior Hunter",
        10: "Skilled Trader",
        15: "Expert Sniper",
        20: "Master Hunter",
        25: "Elite Sniper",
        30: "Legendary Trader",
        40: "Crypto God",
        50: "Divine Sniper 👑"
    }
    
    ACHIEVEMENTS = [
        Achievement(AchievementType.FIRST_BLOOD, "First Blood", "Execute your first trade", "🩸", 100),
        Achievement(AchievementType.PROFIT_STREAK, "Hot Streak", "5 profitable trades in a row", "🔥", 500),
        Achievement(AchievementType.DIAMOND_HANDS, "Diamond Hands", "Hold through a 50% dip and profit", "💎", 1000),
        Achievement(AchievementType.WHALE_HUNTER, "Whale Hunter", "Catch a whale-backed token early", "🐋", 750),
        Achievement(AchievementType.NIGHT_OWL, "Night Owl", "Trade profitably at 3 AM", "🦉", 300),
        Achievement(AchievementType.EARLY_BIRD, "Early Bird", "Catch a 10x within first hour", "🐦", 800),
        Achievement(AchievementType.LEGENDARY_FINDER, "Legend Hunter", "Find a LEGENDARY signal", "🌟", 1500),
        Achievement(AchievementType.HUNDRED_TRADES, "Century Club", "Execute 100 trades", "💯", 1000),
        Achievement(AchievementType.THOUSAND_SOL, "Thousandaire", "Profit 1000 SOL total", "💰", 5000),
        Achievement(AchievementType.PERFECT_WEEK, "Perfect Week", "7 days with 80%+ win rate", "🏆", 2000),
    ]
    
    def __init__(self):
        self.user_progress: Dict[str, UserProgress] = {}
        
    def get_or_create_progress(self, user_id: str) -> UserProgress:
        """Get or create user progress"""
        if user_id not in self.user_progress:
            self.user_progress[user_id] = UserProgress(
                user_id=user_id,
                achievements=[Achievement(**a.__dict__) for a in self.ACHIEVEMENTS]
            )
        return self.user_progress[user_id]
    
    def add_xp(self, user_id: str, amount: int, reason: str = "") -> Tuple[int, bool]:
        """
        Add XP to user. Returns (new_level, did_level_up)
        """
        progress = self.get_or_create_progress(user_id)
        old_level = progress.level
        
        progress.xp += amount
        
        # Level up check (100 XP per level, scaling)
        xp_for_next = progress.level * 100
        while progress.xp >= xp_for_next:
            progress.xp -= xp_for_next
            progress.level += 1
            xp_for_next = progress.level * 100
            
        # Update rank title
        for level, title in sorted(self.RANK_TITLES.items(), reverse=True):
            if progress.level >= level:
                progress.rank_title = title
                break
                
        return progress.level, progress.level > old_level
    
    def record_trade(self, user_id: str, profit_sol: float, is_win: bool):
        """Record a trade and check for achievements"""
        progress = self.get_or_create_progress(user_id)
        
        progress.total_trades += 1
        progress.total_profit_sol += profit_sol
        
        if is_win:
            progress.win_streak += 1
            progress.best_streak = max(progress.best_streak, progress.win_streak)
        else:
            progress.win_streak = 0
            
        # XP rewards
        base_xp = 10 if is_win else 5
        if progress.win_streak >= 3:
            base_xp *= 2  # Double XP during streaks
            
        self.add_xp(user_id, base_xp)
        
        # Check achievements
        self._check_achievements(user_id)
        
    def _check_achievements(self, user_id: str):
        """Check and unlock achievements"""
        progress = self.get_or_create_progress(user_id)
        
        for achievement in progress.achievements:
            if achievement.unlocked:
                continue
                
            unlocked = False
            
            if achievement.type == AchievementType.FIRST_BLOOD and progress.total_trades >= 1:
                unlocked = True
            elif achievement.type == AchievementType.PROFIT_STREAK and progress.win_streak >= 5:
                unlocked = True
            elif achievement.type == AchievementType.HUNDRED_TRADES and progress.total_trades >= 100:
                unlocked = True
            elif achievement.type == AchievementType.THOUSAND_SOL and progress.total_profit_sol >= 1000:
                unlocked = True
                
            if unlocked:
                achievement.unlocked = True
                achievement.unlocked_at = datetime.utcnow()
                self.add_xp(user_id, achievement.xp_reward, f"Achievement: {achievement.name}")
                
    def get_leaderboard(self, limit: int = 10) -> List[dict]:
        """Get top users by XP"""
        sorted_users = sorted(
            self.user_progress.values(),
            key=lambda u: (u.level, u.xp),
            reverse=True
        )[:limit]
        
        return [
            {
                "rank": i + 1,
                "user_id": u.user_id[:8] + "...",
                "level": u.level,
                "xp": u.xp,
                "title": u.rank_title,
                "wins": u.total_trades,
                "streak": u.best_streak
            }
            for i, u in enumerate(sorted_users)
        ]


# ============================================================
# 🛡️ DIVINE PROTECTION LAYER
# Multi-level safety system
# ============================================================

class ThreatLevel(Enum):
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ProtectionResult:
    """Result of protection check"""
    passed: bool
    threat_level: ThreatLevel
    threats_detected: List[str]
    protection_score: float  # 0-100
    recommendation: str


class DivineProtectionLayer:
    """
    🛡️ Divine Protection System
    
    A multi-layer defense system that protects users from:
    - Rug pulls
    - Honeypots
    - Tax tokens
    - Pump and dumps
    - Scam contracts
    
    Uses multiple independent verification layers.
    """
    
    def __init__(self):
        self.known_scammers: Set[str] = set()
        self.verified_contracts: Set[str] = set()
        self.protection_stats = {
            "rugs_blocked": 0,
            "honeypots_detected": 0,
            "users_saved": 0,
            "sol_protected": 0.0
        }
        
    async def full_protection_check(self, mint: str, contract_data: dict) -> ProtectionResult:
        """
        Run all protection checks.
        Returns combined protection result.
        """
        threats = []
        
        # Layer 1: Contract Analysis
        if not contract_data.get("mintAuthorityRevoked"):
            threats.append("⚠️ Mint authority NOT revoked (infinite supply risk)")
        if not contract_data.get("freezeAuthorityRevoked"):
            threats.append("🚨 Freeze authority active (funds can be frozen)")
            
        # Layer 2: Liquidity Analysis
        if not contract_data.get("liquidityLocked"):
            threats.append("⚠️ Liquidity NOT locked (rug pull risk)")
        if contract_data.get("lpBurnPercent", 0) < 50:
            threats.append("⚠️ Less than 50% LP burned")
            
        # Layer 3: Holder Analysis
        top_holder = contract_data.get("top1HolderPercent", 100)
        if top_holder > 30:
            threats.append(f"⚠️ Top holder owns {top_holder}% (whale dump risk)")
        dev_wallet = contract_data.get("devWalletPercent", 100)
        if dev_wallet > 10:
            threats.append(f"⚠️ Dev wallet holds {dev_wallet}%")
            
        # Layer 4: Tax Analysis
        buy_tax = contract_data.get("buyTax", 0)
        sell_tax = contract_data.get("sellTax", 0)
        if buy_tax > 5:
            threats.append(f"⚠️ High buy tax: {buy_tax}%")
        if sell_tax > 5:
            threats.append(f"🚨 High sell tax: {sell_tax}% (honeypot risk)")
        if sell_tax > 20:
            threats.append("🚨🚨 HONEYPOT DETECTED: Cannot sell!")
            
        # Layer 5: Scammer Database
        deployer = contract_data.get("deployer", "")
        if deployer in self.known_scammers:
            threats.append("🚨🚨 KNOWN SCAMMER DEPLOYER!")
            
        # Layer 6: Pattern Detection
        if contract_data.get("hiddenMint"):
            threats.append("🚨 Hidden mint function detected")
        if contract_data.get("hiddenTransferFee"):
            threats.append("🚨 Hidden transfer fee detected")
            
        # Calculate protection score
        protection_score = 100 - (len(threats) * 15)
        protection_score = max(0, protection_score)
        
        # Determine threat level
        if len(threats) == 0:
            threat_level = ThreatLevel.SAFE
            recommendation = "✅ All checks passed. Safe to trade."
        elif len(threats) <= 2:
            threat_level = ThreatLevel.LOW
            recommendation = "⚠️ Minor concerns. Proceed with caution."
        elif len(threats) <= 4:
            threat_level = ThreatLevel.MEDIUM
            recommendation = "⚠️ Multiple risks detected. Use small position."
        elif len(threats) <= 6:
            threat_level = ThreatLevel.HIGH
            recommendation = "🚨 Significant risks. Not recommended."
        else:
            threat_level = ThreatLevel.CRITICAL
            recommendation = "🚨🚨 CRITICAL: DO NOT TRADE!"
            
        passed = threat_level.value <= ThreatLevel.MEDIUM.value
        
        if not passed:
            self.protection_stats["rugs_blocked"] += 1
            
        return ProtectionResult(
            passed=passed,
            threat_level=threat_level,
            threats_detected=threats,
            protection_score=protection_score,
            recommendation=recommendation
        )


# ============================================================
# 📊 AUTO-COMPOUNDING ENGINE
# Reinvest profits automatically
# ============================================================

@dataclass
class CompoundSettings:
    """User's auto-compound settings"""
    enabled: bool = False
    compound_percent: float = 50.0  # % of profits to reinvest
    min_profit_to_compound: float = 0.1  # Min SOL profit to trigger
    max_position_size: float = 2.0  # Max SOL per trade after compounding
    compound_frequency: str = "per_trade"  # per_trade, daily, weekly


class AutoCompoundingEngine:
    """
    📊 Auto-Compounding System
    
    Automatically reinvests profits to compound gains.
    Users can set what % of profits to reinvest.
    """
    
    def __init__(self):
        self.user_settings: Dict[str, CompoundSettings] = {}
        self.compound_history: Dict[str, List[dict]] = {}
        
    def get_settings(self, user_id: str) -> CompoundSettings:
        """Get or create user compound settings"""
        if user_id not in self.user_settings:
            self.user_settings[user_id] = CompoundSettings()
        return self.user_settings[user_id]
    
    def calculate_new_position_size(
        self,
        user_id: str,
        base_size: float,
        profit: float
    ) -> Tuple[float, float]:
        """
        Calculate new position size after compounding.
        Returns: (new_size, amount_compounded)
        """
        settings = self.get_settings(user_id)
        
        if not settings.enabled:
            return base_size, 0.0
            
        if profit < settings.min_profit_to_compound:
            return base_size, 0.0
            
        compound_amount = profit * (settings.compound_percent / 100)
        new_size = min(
            base_size + compound_amount,
            settings.max_position_size
        )
        
        # Record compound event
        if user_id not in self.compound_history:
            self.compound_history[user_id] = []
        self.compound_history[user_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "profit": profit,
            "compounded": compound_amount,
            "new_size": new_size
        })
        
        return new_size, compound_amount
    
    def get_compound_stats(self, user_id: str) -> dict:
        """Get compounding statistics for user"""
        history = self.compound_history.get(user_id, [])
        
        if not history:
            return {
                "total_compounded": 0.0,
                "compound_events": 0,
                "avg_compound": 0.0,
                "growth_rate": 0.0
            }
            
        total_compounded = sum(h["compounded"] for h in history)
        
        return {
            "total_compounded": total_compounded,
            "compound_events": len(history),
            "avg_compound": total_compounded / len(history),
            "growth_rate": (history[-1]["new_size"] / history[0]["new_size"] - 1) * 100
        }


# ============================================================
# 🌊 MARKET REGIME DETECTION
# Adapt to bull/bear/crab markets
# ============================================================

class MarketRegime(Enum):
    BULL = "bull"
    BEAR = "bear"
    CRAB = "crab"  # Sideways
    VOLATILE = "volatile"


class MarketRegimeDetector:
    """
    🌊 Market Regime Detection
    
    Identifies the current market regime and adapts
    trading strategy accordingly:
    - BULL: Aggressive entries, wider TPs
    - BEAR: Conservative, quick exits
    - CRAB: Scalping mode
    - VOLATILE: Tight stops, small positions
    """
    
    def __init__(self):
        self.current_regime = MarketRegime.CRAB
        self.regime_history: List[Tuple[datetime, MarketRegime]] = []
        
    async def detect_regime(self, market_data: dict) -> MarketRegime:
        """
        Analyze market data to detect current regime.
        """
        sol_24h_change = market_data.get("sol_24h_change", 0)
        btc_24h_change = market_data.get("btc_24h_change", 0)
        new_token_volume = market_data.get("pump_fun_volume", 0)
        volatility = market_data.get("volatility_index", 50)
        
        # Bull market: SOL and volume up
        if sol_24h_change > 5 and new_token_volume > 1000000:
            regime = MarketRegime.BULL
        # Bear market: SOL down, low activity
        elif sol_24h_change < -5 and new_token_volume < 500000:
            regime = MarketRegime.BEAR
        # Volatile: High swings
        elif volatility > 70:
            regime = MarketRegime.VOLATILE
        # Crab: Everything else
        else:
            regime = MarketRegime.CRAB
            
        self.current_regime = regime
        self.regime_history.append((datetime.utcnow(), regime))
        
        return regime
    
    def get_strategy_adjustments(self) -> dict:
        """
        Get strategy adjustments based on current regime.
        """
        adjustments = {
            MarketRegime.BULL: {
                "confidence_modifier": -5,  # Take more risks
                "position_mult": 1.3,
                "tp_mult": 1.5,
                "sl_mult": 1.0,
                "max_trades_mult": 1.5,
                "message": "🐂 BULL MARKET: Aggressive mode activated"
            },
            MarketRegime.BEAR: {
                "confidence_modifier": 10,  # Be more selective
                "position_mult": 0.5,
                "tp_mult": 0.8,
                "sl_mult": 0.7,
                "max_trades_mult": 0.5,
                "message": "🐻 BEAR MARKET: Defensive mode activated"
            },
            MarketRegime.CRAB: {
                "confidence_modifier": 0,
                "position_mult": 1.0,
                "tp_mult": 1.0,
                "sl_mult": 1.0,
                "max_trades_mult": 1.0,
                "message": "🦀 CRAB MARKET: Balanced mode"
            },
            MarketRegime.VOLATILE: {
                "confidence_modifier": 15,  # Very selective
                "position_mult": 0.3,
                "tp_mult": 2.0,  # Wide TPs for big moves
                "sl_mult": 0.5,   # Tight SLs
                "max_trades_mult": 0.3,
                "message": "🌊 VOLATILE: Scalping mode with tight stops"
            }
        }
        
        return adjustments[self.current_regime]


# ============================================================
# 🌐 GLOBAL INSTANCES
# ============================================================

ai_sentiment = AISentimentEngine()
cascade_detector = MomentumCascadeDetector()
smart_money = SmartMoneyTracker()
gamification = GamificationEngine()
divine_protection = DivineProtectionLayer()
auto_compound = AutoCompoundingEngine()
market_regime = MarketRegimeDetector()
