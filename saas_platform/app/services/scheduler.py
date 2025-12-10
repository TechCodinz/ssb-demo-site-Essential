"""
Sol Sniper Bot PRO - Background Tasks
Subscription expiration checker, heartbeat monitor, daily summary.
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.models import CloudUser, CloudHeartbeat, CloudActivityLog


async def expire_subscriptions():
    """
    Check for expired subscriptions and mark users inactive.
    Runs every 12 hours.
    """
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        
        # Find active users whose subscription has expired
        result = await db.execute(
            select(CloudUser).where(
                and_(
                    CloudUser.is_active == True,
                    CloudUser.expires_at < now
                )
            )
        )
        expired_users = result.scalars().all()
        
        count = 0
        for user in expired_users:
            user.is_active = False
            user.suspension_reason = "Subscription expired"
            
            # Log the auto-expiration
            log = CloudActivityLog(
                cloud_user_id=user.id,
                action="auto_expired",
                details={"expired_at": user.expires_at.isoformat()}
            )
            db.add(log)
            count += 1
        
        await db.commit()
        
        if count > 0:
            print(f"[SCHEDULER] Expired {count} subscriptions")
        
        return count


async def check_inactive_heartbeats():
    """
    Check for users without heartbeat for 3+ minutes.
    Marks them as potentially inactive (but doesn't suspend).
    """
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=3)
        
        # Find users who haven't sent heartbeat in 3 minutes
        result = await db.execute(
            select(CloudUser).where(
                and_(
                    CloudUser.is_active == True,
                    CloudUser.last_heartbeat_at < cutoff
                )
            )
        )
        inactive = result.scalars().all()
        
        # Just log it (don't suspend - they may be offline)
        for user in inactive:
            log = CloudActivityLog(
                cloud_user_id=user.id,
                action="heartbeat_timeout",
                details={
                    "last_heartbeat": user.last_heartbeat_at.isoformat() if user.last_heartbeat_at else None
                }
            )
            db.add(log)
        
        await db.commit()
        
        return len(inactive)


async def detect_suspicious_activity():
    """
    Detect potential token abuse:
    - Multiple IPs in short time
    - Multiple devices
    - Unusual patterns
    """
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        
        # Find users with >5 different IPs in last 24 hours
        result = await db.execute(
            select(CloudUser).where(
                and_(
                    CloudUser.is_active == True,
                    CloudUser.ip_changes_today >= 5
                )
            )
        )
        suspicious = result.scalars().all()
        
        for user in suspicious:
            if not user.is_suspicious:
                user.is_suspicious = True
                
                log = CloudActivityLog(
                    cloud_user_id=user.id,
                    action="abuse_detected",
                    details={"reason": "too_many_ip_changes", "count": user.ip_changes_today}
                )
                db.add(log)
                
                # TODO: Send admin notification
                print(f"[SECURITY] Suspicious activity: {user.email} - {user.ip_changes_today} IP changes")
        
        await db.commit()
        
        return len(suspicious)


async def reset_daily_counters():
    """
    Reset daily IP change counters at midnight.
    """
    async with AsyncSessionLocal() as db:
        # Reset all IP change counters and login attempts
        await db.execute(
            CloudUser.__table__.update().values(ip_changes_today=0, login_attempts_today=0)
        )
        await db.commit()
        print("[SCHEDULER] Daily counters reset")


async def send_expiry_reminders():
    """
    Send expiry reminders at 7, 3, and 1 day before expiration.
    """
    from app.services.email_service import send_expiry_reminder
    
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        
        # Check 7, 3, 1 day periods
        reminder_days = [7, 3, 1]
        
        for days in reminder_days:
            start = now + timedelta(days=days)
            end = start + timedelta(hours=12)  # 12-hour window
            
            result = await db.execute(
                select(CloudUser).where(
                    and_(
                        CloudUser.is_active == True,
                        CloudUser.expires_at >= start,
                        CloudUser.expires_at < end
                    )
                )
            )
            users = result.scalars().all()
            
            for user in users:
                await send_expiry_reminder(
                    user.email, 
                    days, 
                    user.plan, 
                    user.expires_at.strftime("%Y-%m-%d %H:%M UTC")
                )
                
                # Log the reminder
                log = CloudActivityLog(
                    cloud_user_id=user.id,
                    action=f"expiry_reminder_{days}d",
                    details={"expires_at": user.expires_at.isoformat()}
                )
                db.add(log)
        
        await db.commit()
        print("[SCHEDULER] Expiry reminders sent")


async def generate_daily_summary():
    """
    Generate daily summary for admin.
    """
    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        # New users
        new_result = await db.execute(
            select(func.count(CloudUser.id)).where(
                CloudUser.created_at > yesterday
            )
        )
        new_users = new_result.scalar() or 0
        
        # Renewals
        renewal_result = await db.execute(
            select(func.count(CloudActivityLog.id)).where(
                and_(
                    CloudActivityLog.action == "renewal",
                    CloudActivityLog.timestamp > yesterday
                )
            )
        )
        renewals = renewal_result.scalar() or 0
        
        # Active
        active_result = await db.execute(
            select(func.count(CloudUser.id)).where(
                and_(
                    CloudUser.is_active == True,
                    CloudUser.expires_at > now
                )
            )
        )
        active = active_result.scalar() or 0
        
        # Expired
        expired_result = await db.execute(
            select(func.count(CloudUser.id)).where(
                CloudUser.expires_at <= now
            )
        )
        expired = expired_result.scalar() or 0
        
        summary = f"""
        📊 SSB Cloud Daily Summary
        ━━━━━━━━━━━━━━━━━━
        New Users: {new_users}
        Renewals: {renewals}
        Active: {active}
        Expired: {expired}
        """
        
        # TODO: Send to admin via Telegram or Email
        print(summary)
        
        return {
            "new_users": new_users,
            "renewals": renewals,
            "active": active,
            "expired": expired
        }


# Scheduler runner
async def run_scheduler():
    """
    Main scheduler loop.
    """
    print("[SCHEDULER] Starting background task scheduler")
    
    while True:
        try:
            # Run every 12 hours: expire subscriptions
            await expire_subscriptions()
            
            # Run every 5 minutes: check heartbeats
            await check_inactive_heartbeats()
            
            # Run every hour: detect abuse
            await detect_suspicious_activity()
            
            # Run every 12 hours: send expiry reminders
            await send_expiry_reminders()
            
        except Exception as e:
            print(f"[SCHEDULER] Error: {e}")
        
        # Sleep for 5 minutes
        await asyncio.sleep(300)


def start_background_tasks():
    """
    Start background scheduler as asyncio task.
    Call this from main.py startup.
    """
    asyncio.create_task(run_scheduler())
