"""
Sol Sniper Bot PRO - License Management Service
Complete license system with HWID management, device limits, and renewal logic.
"""
import asyncio
import secrets
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import CloudUser
from app.services.email_service import (
    send_device_change_email,
    send_expiry_reminder_email,
    send_suspension_email
)

logger = logging.getLogger(__name__)


# ============================================================
# LICENSE CONFIGURATION
# ============================================================

class LicenseStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    PENDING = "pending"


# Plan device limits
PLAN_DEVICE_LIMITS = {
    "ELITE": 3,
    "PRO": 1,
    "STANDARD": 1,
    "DEMO": 1
}

# Plan duration (days) - 0 = lifetime
PLAN_DURATION = {
    "ELITE": 0,  # Lifetime
    "PRO": 30,
    "STANDARD": 30,
    "DEMO": 7
}


@dataclass
class DeviceInfo:
    """Device information for HWID tracking"""
    hwid: str
    name: str = ""
    ip: str = ""
    browser_fingerprint: str = ""
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    is_approved: bool = True


@dataclass 
class LicenseInfo:
    """Complete license information"""
    license_key: str
    email: str
    plan: str
    status: LicenseStatus
    devices: List[DeviceInfo]
    max_devices: int
    created_at: datetime
    expires_at: Optional[datetime]
    days_remaining: int
    is_lifetime: bool
    cloud_token: Optional[str] = None


# ============================================================
# LICENSE SERVICE
# ============================================================

class LicenseService:
    """
    🔐 Complete License Management System
    
    Features:
    - License key generation and validation
    - HWID/device management
    - Multi-device support for ELITE
    - Device approval workflow
    - Automatic expiry and renewal
    - Suspicious activity detection
    """
    
    def __init__(self):
        self.pending_device_approvals: Dict[str, DeviceInfo] = {}
        self.active_sessions: Dict[str, datetime] = {}  # user_id -> last_activity
    
    # ============================================================
    # LICENSE KEY GENERATION
    # ============================================================
    
    @staticmethod
    def generate_license_key(plan: str) -> str:
        """Generate a unique license key"""
        prefix = f"SSB-{plan[:3].upper()}"
        random_part = secrets.token_hex(8).upper()
        return f"{prefix}-{random_part[:4]}-{random_part[4:8]}-{random_part[8:12]}"
    
    @staticmethod
    def generate_cloud_token() -> str:
        """Generate a cloud access token"""
        return f"CLOUD-{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def hash_hwid(hwid: str) -> str:
        """Hash HWID for storage"""
        return hashlib.sha256(hwid.encode()).hexdigest()[:32]
    
    # ============================================================
    # LICENSE VALIDATION
    # ============================================================
    
    async def validate_license(
        self,
        db: AsyncSession,
        license_key: str,
        hwid: str,
        email: str,
        ip: str = ""
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validate license and HWID combination.
        Returns: (valid, message, cloud_token)
        """
        # Find user by license key (token)
        result = await db.execute(
            select(CloudUser).where(CloudUser.token == license_key)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False, "Invalid license key", None
        
        # Check email matches
        if user.email.lower() != email.lower():
            logger.warning(f"License/email mismatch: {license_key} vs {email}")
            return False, "License key does not match this email", None
        
        # Check suspension
        if not user.is_active:
            return False, f"License suspended: {user.suspension_reason or 'Contact support'}", None
        
        # Check locked
        if user.is_locked:
            return False, "Account locked due to suspicious activity. Check your email.", None
        
        # Check expiry
        if user.expires_at and user.expires_at < datetime.utcnow():
            return False, "License expired. Please renew to continue.", None
        
        # Check HWID
        hwid_hash = self.hash_hwid(hwid)
        max_devices = PLAN_DEVICE_LIMITS.get(user.plan, 1)
        
        # Get current devices
        current_devices = user.login_ips or []  # We'll store devices as JSON
        
        if user.bound_device_id:
            # Check if this HWID is the bound one
            if user.bound_device_id != hwid_hash:
                # New device detected
                current_device_count = len(set(d.get("hwid") for d in current_devices if d.get("hwid")))
                
                if current_device_count >= max_devices:
                    # Over device limit
                    await self._trigger_new_device_alert(db, user, hwid, ip)
                    return False, f"Device limit reached ({max_devices} max). Check your email to approve this device.", None
                else:
                    # Can add new device
                    await self._add_new_device(db, user, hwid, ip)
                    logger.info(f"New device added for user {user.email}")
        else:
            # First device binding
            user.bound_device_id = hwid_hash
            user.binding_locked = True
            await db.commit()
        
        # Update last login
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip
        await db.commit()
        
        # Generate cloud token
        cloud_token = self.generate_cloud_token()
        
        return True, "License valid", cloud_token
    
    async def _trigger_new_device_alert(
        self,
        db: AsyncSession,
        user: CloudUser,
        hwid: str,
        ip: str
    ):
        """Trigger new device approval workflow"""
        approval_token = secrets.token_urlsafe(32)
        
        self.pending_device_approvals[approval_token] = DeviceInfo(
            hwid=self.hash_hwid(hwid),
            ip=ip,
            is_approved=False
        )
        
        # Send email
        try:
            await send_device_change_email(
                to_email=user.email,
                approval_token=approval_token,
                device_ip=ip
            )
        except Exception as e:
            logger.error(f"Failed to send device alert email: {e}")
    
    async def _add_new_device(
        self,
        db: AsyncSession,
        user: CloudUser,
        hwid: str,
        ip: str
    ):
        """Add a new device to user's device list"""
        devices = user.login_ips or []
        devices.append({
            "hwid": self.hash_hwid(hwid),
            "ip": ip,
            "added_at": datetime.utcnow().isoformat()
        })
        user.login_ips = devices
        await db.commit()
    
    # ============================================================
    # DEVICE MANAGEMENT
    # ============================================================
    
    async def approve_device(
        self,
        db: AsyncSession,
        user_id: str,
        approval_token: str
    ) -> Tuple[bool, str]:
        """Approve a pending device"""
        device = self.pending_device_approvals.get(approval_token)
        
        if not device:
            return False, "Invalid or expired approval token"
        
        result = await db.execute(
            select(CloudUser).where(CloudUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False, "User not found"
        
        # Add device
        devices = user.login_ips or []
        devices.append({
            "hwid": device.hwid,
            "ip": device.ip,
            "added_at": datetime.utcnow().isoformat(),
            "approved": True
        })
        user.login_ips = devices
        await db.commit()
        
        # Remove from pending
        del self.pending_device_approvals[approval_token]
        
        return True, "Device approved successfully"
    
    async def deny_device(
        self,
        db: AsyncSession,
        user_id: str,
        approval_token: str
    ) -> Tuple[bool, str]:
        """Deny a pending device"""
        if approval_token in self.pending_device_approvals:
            del self.pending_device_approvals[approval_token]
            logger.warning(f"Device denied for user {user_id}")
            return True, "Device denied"
        return False, "Invalid or expired approval token"
    
    async def reset_devices(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Tuple[bool, str]:
        """Reset all devices for a user (admin action)"""
        result = await db.execute(
            select(CloudUser).where(CloudUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False, "User not found"
        
        user.bound_device_id = None
        user.binding_locked = False
        user.login_ips = []
        user.device_reset_at = datetime.utcnow()
        await db.commit()
        
        logger.info(f"Devices reset for user {user.email}")
        return True, "All devices reset successfully"
    
    async def get_user_devices(
        self,
        db: AsyncSession,
        user_id: str
    ) -> List[dict]:
        """Get list of user's registered devices"""
        result = await db.execute(
            select(CloudUser).where(CloudUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return []
        
        devices = user.login_ips or []
        return [
            {
                "hwid": d.get("hwid", "")[:8] + "...",  # Truncated for display
                "ip": d.get("ip", ""),
                "added_at": d.get("added_at", ""),
                "approved": d.get("approved", True)
            }
            for d in devices
        ]
    
    # ============================================================
    # SUBSCRIPTION RENEWAL
    # ============================================================
    
    async def renew_subscription(
        self,
        db: AsyncSession,
        user_id: str,
        plan: str,
        days: int = 30
    ) -> Tuple[bool, str]:
        """Renew a subscription"""
        result = await db.execute(
            select(CloudUser).where(CloudUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False, "User not found"
        
        now = datetime.utcnow()
        
        # Calculate new expiry
        if user.expires_at and user.expires_at > now:
            # Extend from current expiry
            new_expiry = user.expires_at + timedelta(days=days)
        else:
            # Renew from now
            new_expiry = now + timedelta(days=days)
        
        # Update user
        user.plan = plan
        user.expires_at = new_expiry
        user.is_active = True
        user.trading_mode = "LIVE"
        
        await db.commit()
        
        logger.info(f"Subscription renewed for {user.email}: {plan} until {new_expiry}")
        return True, f"Subscription renewed until {new_expiry.strftime('%Y-%m-%d')}"
    
    async def check_expiring_subscriptions(
        self,
        db: AsyncSession
    ) -> List[CloudUser]:
        """Check for subscriptions expiring soon"""
        now = datetime.utcnow()
        expiry_warning = now + timedelta(days=3)
        
        result = await db.execute(
            select(CloudUser).where(
                CloudUser.is_active == True,
                CloudUser.expires_at != None,
                CloudUser.expires_at <= expiry_warning,
                CloudUser.expires_at > now
            )
        )
        
        return result.scalars().all()
    
    async def expire_subscriptions(
        self,
        db: AsyncSession
    ) -> int:
        """Expire subscriptions that are past due"""
        now = datetime.utcnow()
        
        result = await db.execute(
            select(CloudUser).where(
                CloudUser.is_active == True,
                CloudUser.expires_at != None,
                CloudUser.expires_at < now
            )
        )
        
        expired_users = result.scalars().all()
        count = 0
        
        for user in expired_users:
            user.is_active = False
            user.trading_mode = "FROZEN"
            count += 1
            
            # Send expiry email
            try:
                await send_expiry_reminder_email(user.email, expired=True)
            except:
                pass
        
        await db.commit()
        
        if count > 0:
            logger.info(f"Expired {count} subscriptions")
        
        return count
    
    # ============================================================
    # SECURITY & FRAUD DETECTION
    # ============================================================
    
    async def check_suspicious_activity(
        self,
        db: AsyncSession,
        user_id: str,
        ip: str,
        hwid: str
    ) -> Tuple[bool, str]:
        """
        Check for suspicious patterns:
        - Multiple failed logins
        - Too many HWID changes
        - Multiple devices in same minute
        """
        result = await db.execute(
            select(CloudUser).where(CloudUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False, "User not found"
        
        suspicious = False
        reason = ""
        
        # Check failed login attempts
        if user.login_attempts_today >= 5:
            suspicious = True
            reason = "Too many failed login attempts"
        
        # Check device changes
        devices = user.login_ips or []
        recent_devices = [
            d for d in devices
            if d.get("added_at") and 
            datetime.fromisoformat(d["added_at"]) > datetime.utcnow() - timedelta(hours=1)
        ]
        
        if len(recent_devices) >= 3:
            suspicious = True
            reason = "Too many device changes in short time"
        
        # Check IP changes
        if user.ip_changes_today >= 10:
            suspicious = True
            reason = "Excessive IP changes"
        
        if suspicious:
            user.is_suspicious = True
            user.is_locked = True
            user.suspension_reason = reason
            await db.commit()
            
            # Send security email
            try:
                await send_suspension_email(user.email, reason)
            except:
                pass
            
            logger.warning(f"User {user.email} flagged suspicious: {reason}")
            return True, reason
        
        return False, ""
    
    async def suspend_user(
        self,
        db: AsyncSession,
        user_id: str,
        reason: str,
        admin_id: str = ""
    ) -> Tuple[bool, str]:
        """Suspend a user's license"""
        result = await db.execute(
            select(CloudUser).where(CloudUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False, "User not found"
        
        user.is_active = False
        user.suspension_reason = reason
        user.trading_mode = "FROZEN"
        await db.commit()
        
        # Send suspension email
        try:
            await send_suspension_email(user.email, reason)
        except:
            pass
        
        logger.warning(f"User {user.email} suspended by {admin_id}: {reason}")
        return True, "User suspended"
    
    async def reactivate_user(
        self,
        db: AsyncSession,
        user_id: str,
        admin_id: str = ""
    ) -> Tuple[bool, str]:
        """Reactivate a suspended user"""
        result = await db.execute(
            select(CloudUser).where(CloudUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False, "User not found"
        
        user.is_active = True
        user.is_locked = False
        user.is_suspicious = False
        user.suspension_reason = None
        user.login_attempts_today = 0
        user.trading_mode = "LIVE"
        await db.commit()
        
        logger.info(f"User {user.email} reactivated by {admin_id}")
        return True, "User reactivated"
    
    # ============================================================
    # LICENSE INFO
    # ============================================================
    
    async def get_license_info(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Optional[LicenseInfo]:
        """Get complete license information"""
        result = await db.execute(
            select(CloudUser).where(CloudUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Calculate days remaining
        days_remaining = 0
        is_lifetime = PLAN_DURATION.get(user.plan, 30) == 0
        
        if user.expires_at and not is_lifetime:
            delta = user.expires_at - datetime.utcnow()
            days_remaining = max(0, delta.days)
        elif is_lifetime:
            days_remaining = -1  # Lifetime indicator
        
        # Get devices
        devices = []
        for d in (user.login_ips or []):
            devices.append(DeviceInfo(
                hwid=d.get("hwid", ""),
                ip=d.get("ip", ""),
                is_approved=d.get("approved", True)
            ))
        
        # Determine status
        if not user.is_active:
            status = LicenseStatus.SUSPENDED
        elif user.expires_at and user.expires_at < datetime.utcnow():
            status = LicenseStatus.EXPIRED
        else:
            status = LicenseStatus.ACTIVE
        
        return LicenseInfo(
            license_key=user.token,
            email=user.email,
            plan=user.plan,
            status=status,
            devices=devices,
            max_devices=PLAN_DEVICE_LIMITS.get(user.plan, 1),
            created_at=user.created_at,
            expires_at=user.expires_at,
            days_remaining=days_remaining,
            is_lifetime=is_lifetime
        )


# ============================================================
# GLOBAL INSTANCE
# ============================================================

license_service = LicenseService()
