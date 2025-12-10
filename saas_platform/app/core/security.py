"""
Sol Sniper Bot PRO - Security Middleware
Rate limiting, request validation, and security headers.
"""
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
from collections import defaultdict
from functools import wraps

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


# ============================================================
# IN-MEMORY RATE LIMITER (use Redis in production cluster)
# ============================================================

class RateLimiter:
    """Simple in-memory rate limiter with sliding window."""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.blocked: Dict[str, datetime] = {}
    
    def _clean_old(self, key: str, window_seconds: int):
        """Remove requests outside the time window."""
        cutoff = time.time() - window_seconds
        self.requests[key] = [t for t in self.requests[key] if t > cutoff]
    
    def is_blocked(self, key: str) -> bool:
        """Check if key is temporarily blocked."""
        if key in self.blocked:
            if datetime.utcnow() < self.blocked[key]:
                return True
            del self.blocked[key]
        return False
    
    def block(self, key: str, minutes: int = 15):
        """Block a key for specified minutes."""
        self.blocked[key] = datetime.utcnow() + timedelta(minutes=minutes)
    
    def check(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """
        Check if request is allowed.
        Returns True if allowed, False if rate limited.
        """
        if self.is_blocked(key):
            return False
        
        self._clean_old(key, window_seconds)
        
        if len(self.requests[key]) >= limit:
            return False
        
        self.requests[key].append(time.time())
        return True
    
    def get_remaining(self, key: str, limit: int, window_seconds: int = 60) -> int:
        """Get remaining requests in window."""
        self._clean_old(key, window_seconds)
        return max(0, limit - len(self.requests[key]))


# Global rate limiter instance
rate_limiter = RateLimiter()


# ============================================================
# SECURITY HEADERS MIDDLEWARE
# ============================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


# ============================================================
# REQUEST VALIDATION
# ============================================================

def get_client_identifier(request: Request) -> str:
    """Get unique identifier for client (IP + User-Agent hash)."""
    ip = get_real_ip(request)
    ua = request.headers.get("user-agent", "unknown")
    return hashlib.md5(f"{ip}:{ua}".encode()).hexdigest()[:16]


def get_real_ip(request: Request) -> str:
    """Extract real client IP from request."""
    # Check common proxy headers
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    cf_ip = request.headers.get("cf-connecting-ip")  # Cloudflare
    if cf_ip:
        return cf_ip
    
    return request.client.host if request.client else "unknown"


def validate_token_format(token: str) -> bool:
    """Validate cloud token format: CLOUD-{PLAN}-{12_CHARS}."""
    if not token:
        return False
    
    parts = token.split("-")
    if len(parts) != 3:
        return False
    
    if parts[0] != "CLOUD":
        return False
    
    if parts[1] not in ["STANDARD", "PRO", "ELITE"]:
        return False
    
    if len(parts[2]) != 12:
        return False
    
    # Check alphanumeric
    if not parts[2].isalnum():
        return False
    
    return True


def validate_admin_token_format(token: str) -> bool:
    """Validate admin token format: ADMIN-MASTER-{16_CHARS}."""
    if not token:
        return False
    
    parts = token.split("-")
    if len(parts) != 3:
        return False
    
    if parts[0] != "ADMIN" or parts[1] != "MASTER":
        return False
    
    if len(parts[2]) != 16:
        return False
    
    return True


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Sanitize string input."""
    if not value:
        return ""
    value = value.replace("\x00", "")
    value = value[:max_length]
    return value.strip()


def sanitize_email(email: str) -> str:
    """Sanitize and lowercase email."""
    return sanitize_string(email, 255).lower()


# ============================================================
# RATE LIMITING DECORATORS
# ============================================================

def rate_limit(limit: int, window: int = 60, key_func: Callable = None):
    """Rate limiting decorator for endpoints."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request:
                if key_func:
                    key = key_func(request)
                else:
                    key = f"{func.__name__}:{get_real_ip(request)}"
                
                if not rate_limiter.check(key, limit, window):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Try again in {window} seconds."
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# ABUSE DETECTION
# ============================================================

class AbuseDetector:
    """Detect suspicious activity patterns."""
    
    def __init__(self):
        self.ip_history: Dict[str, list] = defaultdict(list)
        self.device_switches: Dict[str, int] = defaultdict(int)
        self.failed_attempts: Dict[str, int] = defaultdict(int)
    
    def track_ip(self, user_id: str, ip: str) -> dict:
        """Track IP for user and detect abuse."""
        history = self.ip_history[user_id]
        
        if not history or history[-1] != ip:
            history.append(ip)
            self.ip_history[user_id] = history[-20:]
        
        unique_ips = len(set(history[-10:]))
        
        return {
            "unique_ips_recent": unique_ips,
            "is_suspicious": unique_ips >= 5,
            "rapid_switching": len(history) > 5 and unique_ips > 3
        }
    
    def track_failed_login(self, identifier: str) -> int:
        """Track failed login attempts."""
        self.failed_attempts[identifier] += 1
        return self.failed_attempts[identifier]
    
    def reset_failed_logins(self, identifier: str):
        """Reset failed login counter."""
        self.failed_attempts[identifier] = 0
    
    def is_blocked(self, identifier: str) -> bool:
        """Check if identifier should be blocked."""
        return self.failed_attempts.get(identifier, 0) >= settings.MAX_FAILED_LOGINS


# Global abuse detector
abuse_detector = AbuseDetector()
