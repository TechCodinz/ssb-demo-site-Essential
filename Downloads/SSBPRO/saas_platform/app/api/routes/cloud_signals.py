"""
Sol Sniper Bot PRO - Trading Signal API
Exposes algorithm signals and stats to the frontend dashboard.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.routes.cloud_auth import get_current_cloud_user
from app.models.models import CloudUser
from app.worker.ultra_algorithm import (
    UltraSnipeAlgorithm, ProfitOptimizer, SignalStrength
)

router = APIRouter(prefix="/cloud/signals", tags=["Trading Signals"])


# ============================================================
# SCHEMAS
# ============================================================

class SignalSummary(BaseModel):
    signal_id: str
    mint: str
    confidence: float
    signal_strength: str
    reasons: List[str]
    entry_price: float
    target_tp: float
    target_sl: float
    timestamp: str


class AlgorithmStats(BaseModel):
    version: str
    plan: str
    min_confidence_threshold: int
    aggressive_mode: bool
    trailing_stop_enabled: bool
    dynamic_tp_enabled: bool
    tokens_analyzed_today: int
    signals_generated_today: int
    legendary_signals: int
    ultra_signals: int
    strong_signals: int


class PerformanceMetrics(BaseModel):
    win_rate: float
    avg_win_percent: float
    avg_loss_percent: float
    profit_factor: float
    best_hours_utc: List[int]
    total_trades: int
    recommendation: str


# ============================================================
# GLOBAL TRACKER
# ============================================================

class SignalTracker:
    """Tracks signals across all users for analytics"""
    
    def __init__(self):
        self.daily_stats = {
            "tokens_analyzed": 0,
            "signals_generated": 0,
            "legendary": 0,
            "ultra": 0,
            "strong": 0,
            "moderate": 0,
            "weak": 0,
        }
        self.recent_signals: List[dict] = []
        self.last_reset = datetime.utcnow().date()
        
    def record_signal(self, signal: dict, strength: SignalStrength):
        """Record a generated signal"""
        # Reset daily if new day
        if datetime.utcnow().date() != self.last_reset:
            self.daily_stats = {k: 0 for k in self.daily_stats}
            self.last_reset = datetime.utcnow().date()
            
        self.daily_stats["signals_generated"] += 1
        self.daily_stats[strength.name.lower()] += 1
        
        # Keep last 100 signals
        self.recent_signals.append({
            **signal,
            "strength": strength.name,
            "timestamp": datetime.utcnow().isoformat()
        })
        if len(self.recent_signals) > 100:
            self.recent_signals.pop(0)
            
    def record_analysis(self):
        """Record a token analysis"""
        self.daily_stats["tokens_analyzed"] += 1


signal_tracker = SignalTracker()


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/stats", response_model=AlgorithmStats)
async def get_algorithm_stats(user: CloudUser = Depends(get_current_cloud_user)):
    """Get current algorithm stats for user's plan"""
    algo = UltraSnipeAlgorithm(plan=user.plan)
    
    return AlgorithmStats(
        version="Ultra Snipe v3.0",
        plan=user.plan,
        min_confidence_threshold=algo.thresholds["min_confidence"],
        aggressive_mode=algo.thresholds["aggressive_mode"],
        trailing_stop_enabled=algo.thresholds["trailing_stop_enabled"],
        dynamic_tp_enabled=algo.thresholds["dynamic_tp_enabled"],
        tokens_analyzed_today=signal_tracker.daily_stats["tokens_analyzed"],
        signals_generated_today=signal_tracker.daily_stats["signals_generated"],
        legendary_signals=signal_tracker.daily_stats["legendary"],
        ultra_signals=signal_tracker.daily_stats["ultra"],
        strong_signals=signal_tracker.daily_stats["strong"]
    )


@router.get("/recent", response_model=List[SignalSummary])
async def get_recent_signals(
    limit: int = 20,
    min_strength: str = "MODERATE",
    user: CloudUser = Depends(get_current_cloud_user)
):
    """Get recent trading signals"""
    strength_order = ["WEAK", "MODERATE", "STRONG", "ULTRA", "LEGENDARY"]
    min_index = strength_order.index(min_strength) if min_strength in strength_order else 0
    
    filtered = [
        s for s in signal_tracker.recent_signals
        if strength_order.index(s["strength"]) >= min_index
    ]
    
    return [
        SignalSummary(
            signal_id=s.get("id", ""),
            mint=s.get("mint", "")[:12],
            confidence=s.get("confidence", 0),
            signal_strength=s.get("strength", "MODERATE"),
            reasons=s.get("reasons", [])[:3],
            entry_price=s.get("entry_price", 0),
            target_tp=s.get("target_tp", 0),
            target_sl=s.get("target_sl", 0),
            timestamp=s.get("timestamp", "")
        )
        for s in filtered[-limit:]
    ]


@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(user: CloudUser = Depends(get_current_cloud_user)):
    """Get algorithm performance metrics"""
    optimizer = ProfitOptimizer()
    rec = optimizer.get_recommendation()
    
    return PerformanceMetrics(
        win_rate=float(rec["win_rate"].rstrip("%")),
        avg_win_percent=float(rec["avg_win"].lstrip("+").rstrip("%")),
        avg_loss_percent=float(rec["avg_loss"].lstrip("-").rstrip("%")),
        profit_factor=rec["profit_factor"],
        best_hours_utc=rec["best_hours_utc"],
        total_trades=rec["total_trades"],
        recommendation=rec["recommendation"]
    )


@router.get("/thresholds")
async def get_plan_thresholds(user: CloudUser = Depends(get_current_cloud_user)):
    """Get all threshold values for user's plan"""
    algo = UltraSnipeAlgorithm(plan=user.plan)
    
    return {
        "plan": user.plan,
        "thresholds": algo.thresholds,
        "signal_weights": {
            "volume_momentum": "18%",
            "liquidity_depth": "15%",
            "holder_quality": "14%",
            "price_action": "13%",
            "security_check": "12%",
            "whale_detection": "10%",
            "social_velocity": "8%",
            "pattern_match": "6%",
            "timing_score": "4%"
        },
        "features": {
            "trailing_stop": algo.thresholds["trailing_stop_enabled"],
            "dynamic_tp_sl": algo.thresholds["dynamic_tp_enabled"],
            "aggressive_mode": algo.thresholds["aggressive_mode"],
            "early_entry_boost": algo.thresholds["early_entry_bonus"] > 0,
            "max_trades_hour": algo.thresholds["max_trades_hour"]
        }
    }
