"""
Sol Sniper Bot PRO - Cloud Engine Manager
Manages cloud trading instances with health monitoring, rate limiting, and crash recovery.
"""
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

from app.core.config import settings


class InstanceStatus(str, Enum):
    """Cloud instance status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    CRASHED = "crashed"
    RESTARTING = "restarting"


@dataclass
class InstanceStats:
    """Statistics for a cloud instance."""
    tokens_scanned: int = 0
    trades_executed: int = 0
    trades_successful: int = 0
    trades_failed: int = 0
    last_trade_at: Optional[datetime] = None
    last_tp_at: Optional[datetime] = None
    last_sl_at: Optional[datetime] = None
    errors_count: int = 0
    uptime_seconds: int = 0
    started_at: Optional[datetime] = None


@dataclass
class CloudInstance:
    """Represents a single cloud trading instance."""
    user_id: str
    license_id: str
    plan: str
    status: InstanceStatus = InstanceStatus.STOPPED
    last_heartbeat: Optional[datetime] = None
    restart_count: int = 0
    stats: InstanceStats = field(default_factory=InstanceStats)
    error_message: Optional[str] = None
    trading_mode: str = "DRY_RUN"  # DRY_RUN or LIVE
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "user_id": self.user_id,
            "license_id": self.license_id,
            "plan": self.plan,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "restart_count": self.restart_count,
            "error_message": self.error_message,
            "trading_mode": self.trading_mode,
            "stats": {
                "tokens_scanned": self.stats.tokens_scanned,
                "trades_executed": self.stats.trades_executed,
                "trades_successful": self.stats.trades_successful,
                "trades_failed": self.stats.trades_failed,
                "errors_count": self.stats.errors_count,
                "uptime_seconds": self.stats.uptime_seconds,
                "started_at": self.stats.started_at.isoformat() if self.stats.started_at else None,
                "last_tp_at": self.stats.last_tp_at.isoformat() if self.stats.last_tp_at else None,
                "last_sl_at": self.stats.last_sl_at.isoformat() if self.stats.last_sl_at else None,
            }
        }


class CloudEngineManager:
    """
    Manages all cloud trading instances.
    Enforces one instance per license, handles health monitoring.
    """
    
    def __init__(self):
        self.instances: Dict[str, CloudInstance] = {}  # license_id -> instance
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
    
    def get_plan_limits(self, plan: str) -> dict:
        """Get limits for a plan."""
        return settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS["DEMO"])
    
    def can_start_instance(self, user_id: str, license_id: str, plan: str) -> tuple:
        """
        Check if user can start a cloud instance.
        Returns (can_start: bool, reason: str)
        """
        # Check if instance already exists for this license
        if license_id in self.instances:
            existing = self.instances[license_id]
            if existing.status in [InstanceStatus.RUNNING, InstanceStatus.STARTING]:
                return False, "Instance already running for this license"
        
        # Check plan limits
        limits = self.get_plan_limits(plan)
        if not limits.get("live_trading"):
            return True, "DRY_RUN only"  # Can start but only dry run
        
        return True, "OK"
    
    async def start_instance(
        self, 
        user_id: str, 
        license_id: str, 
        plan: str,
        trading_mode: str = "DRY_RUN"
    ) -> CloudInstance:
        """Start a new cloud instance for user."""
        can_start, reason = self.can_start_instance(user_id, license_id, plan)
        
        if not can_start and "already running" in reason:
            raise ValueError(reason)
        
        # Check plan allows live trading
        limits = self.get_plan_limits(plan)
        if trading_mode == "LIVE" and not limits.get("live_trading"):
            trading_mode = "DRY_RUN"
        
        # Create or update instance
        instance = CloudInstance(
            user_id=user_id,
            license_id=license_id,
            plan=plan,
            status=InstanceStatus.STARTING,
            trading_mode=trading_mode,
            stats=InstanceStats(started_at=datetime.utcnow())
        )
        
        self.instances[license_id] = instance
        
        # Simulate startup (in real implementation, would start actual bot)
        await asyncio.sleep(0.5)
        instance.status = InstanceStatus.RUNNING
        instance.last_heartbeat = datetime.utcnow()
        
        return instance
    
    async def stop_instance(self, license_id: str) -> bool:
        """Stop a cloud instance."""
        if license_id not in self.instances:
            return False
        
        instance = self.instances[license_id]
        instance.status = InstanceStatus.STOPPED
        
        # Update uptime
        if instance.stats.started_at:
            elapsed = (datetime.utcnow() - instance.stats.started_at).total_seconds()
            instance.stats.uptime_seconds += int(elapsed)
            instance.stats.started_at = None
        
        return True
    
    def get_instance(self, license_id: str) -> Optional[CloudInstance]:
        """Get instance by license ID."""
        return self.instances.get(license_id)
    
    def get_user_instance(self, user_id: str) -> Optional[CloudInstance]:
        """Get instance by user ID (first match)."""
        for instance in self.instances.values():
            if instance.user_id == user_id:
                return instance
        return None
    
    def receive_heartbeat(self, license_id: str) -> bool:
        """Receive heartbeat from instance."""
        instance = self.instances.get(license_id)
        if not instance:
            return False
        
        instance.last_heartbeat = datetime.utcnow()
        
        if instance.status == InstanceStatus.ERROR:
            instance.status = InstanceStatus.RUNNING
            instance.error_message = None
        
        return True
    
    def update_stats(
        self, 
        license_id: str, 
        tokens_scanned: int = 0,
        trade_executed: bool = False,
        trade_success: bool = False,
        tp_hit: bool = False,
        sl_hit: bool = False,
        error: bool = False
    ):
        """Update instance statistics."""
        instance = self.instances.get(license_id)
        if not instance:
            return
        
        instance.stats.tokens_scanned += tokens_scanned
        
        if trade_executed:
            instance.stats.trades_executed += 1
            if trade_success:
                instance.stats.trades_successful += 1
            else:
                instance.stats.trades_failed += 1
            instance.stats.last_trade_at = datetime.utcnow()
        
        if tp_hit:
            instance.stats.last_tp_at = datetime.utcnow()
        
        if sl_hit:
            instance.stats.last_sl_at = datetime.utcnow()
        
        if error:
            instance.stats.errors_count += 1
    
    async def check_instance_health(self):
        """Check health of all instances."""
        now = datetime.utcnow()
        timeout = timedelta(seconds=settings.CLOUD_HEARTBEAT_TIMEOUT)
        
        for license_id, instance in list(self.instances.items()):
            if instance.status != InstanceStatus.RUNNING:
                continue
            
            if instance.last_heartbeat and (now - instance.last_heartbeat) > timeout:
                # Instance appears dead
                if instance.restart_count < settings.CLOUD_MAX_RESTART_ATTEMPTS:
                    # Attempt restart
                    instance.status = InstanceStatus.RESTARTING
                    instance.restart_count += 1
                    instance.error_message = "Heartbeat timeout - restarting"
                    
                    # Simulate restart
                    await asyncio.sleep(1)
                    instance.status = InstanceStatus.RUNNING
                    instance.last_heartbeat = datetime.utcnow()
                else:
                    # Too many restarts - mark as crashed
                    instance.status = InstanceStatus.CRASHED
                    instance.error_message = f"Crashed after {instance.restart_count} restart attempts"
    
    async def start_health_monitor(self):
        """Start background health monitoring."""
        if self._running:
            return
        
        self._running = True
        
        while self._running:
            try:
                await self.check_instance_health()
            except Exception as e:
                print(f"[ENGINE] Health check error: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    def stop_health_monitor(self):
        """Stop health monitoring."""
        self._running = False
    
    def get_all_instances(self) -> list:
        """Get all instances as list of dicts."""
        return [inst.to_dict() for inst in self.instances.values()]
    
    def get_running_count(self) -> int:
        """Get count of running instances."""
        return sum(1 for i in self.instances.values() if i.status == InstanceStatus.RUNNING)
    
    def get_stats_summary(self) -> dict:
        """Get summary statistics across all instances."""
        total_tokens = sum(i.stats.tokens_scanned for i in self.instances.values())
        total_trades = sum(i.stats.trades_executed for i in self.instances.values())
        successful = sum(i.stats.trades_successful for i in self.instances.values())
        
        return {
            "total_instances": len(self.instances),
            "running": self.get_running_count(),
            "stopped": sum(1 for i in self.instances.values() if i.status == InstanceStatus.STOPPED),
            "crashed": sum(1 for i in self.instances.values() if i.status == InstanceStatus.CRASHED),
            "total_tokens_scanned": total_tokens,
            "total_trades": total_trades,
            "successful_trades": successful,
            "success_rate": round(successful / total_trades * 100, 2) if total_trades > 0 else 0
        }


# Global cloud engine manager
cloud_engine = CloudEngineManager()


def start_engine_monitor():
    """Start the cloud engine health monitor as asyncio task."""
    asyncio.create_task(cloud_engine.start_health_monitor())
