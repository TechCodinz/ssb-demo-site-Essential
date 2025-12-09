"""
Sol Sniper Bot PRO - Email Service
Email templates and sending for verification, reminders, and notifications.
"""
import os
import smtplib
import hashlib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional

# SMTP Configuration (from environment)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@ssbpro.cloud")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "SSB Cloud")

# For development: print emails to console
DEV_MODE = os.getenv("EMAIL_DEV_MODE", "true").lower() == "true"


# ============================================================
# EMAIL TEMPLATES
# ============================================================

def get_verification_code_email(code: str, email: str) -> tuple:
    """Email verification code template"""
    subject = "🔐 SSB Cloud - Verification Code"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .logo {{ text-align: center; font-size: 28px; margin-bottom: 30px; }}
            .code-box {{ background: #0f0c29; border-radius: 10px; padding: 25px; text-align: center; margin: 20px 0; }}
            .code {{ font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #00d4ff; font-family: monospace; }}
            .warning {{ color: #888; font-size: 14px; margin-top: 20px; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🚀 SSB Cloud</div>
            <h2 style="text-align: center;">Email Verification</h2>
            <p>Hello,</p>
            <p>Use the following code to verify your email for <strong>{email}</strong>:</p>
            <div class="code-box">
                <div class="code">{code}</div>
            </div>
            <p class="warning">⚠️ This code expires in <strong>5 minutes</strong>.</p>
            <p class="warning">If you didn't request this, please ignore this email.</p>
            <div class="footer">
                Sol Sniper Bot PRO - Cloud Trading Platform<br>
                © 2024 All Rights Reserved
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, html


def get_license_suspended_email(email: str, reason: str) -> tuple:
    """License suspension notification"""
    subject = "⚠️ SSB Cloud - License Suspended"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .alert {{ background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; border-radius: 10px; padding: 20px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center; font-size: 28px; margin-bottom: 30px;">🚀 SSB Cloud</div>
            <h2 style="color: #ef4444;">License Suspended</h2>
            <p>Your cloud trading license has been suspended.</p>
            <div class="alert">
                <strong>Reason:</strong> {reason}
            </div>
            <p>If you believe this is an error, please contact support.</p>
            <p style="margin-top: 30px;">
                <a href="https://t.me/ssbprosupport" style="color: #00d4ff;">Contact Support →</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    return subject, html


def get_expiry_reminder_email(email: str, days_left: int, plan: str, expires_at: str) -> tuple:
    """Subscription expiry reminder"""
    urgency = "⚠️" if days_left <= 3 else "📅"
    color = "#ef4444" if days_left <= 1 else "#f59e0b" if days_left <= 3 else "#00d4ff"
    
    subject = f"{urgency} SSB Cloud - Subscription Expires in {days_left} Day{'s' if days_left != 1 else ''}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .countdown {{ font-size: 48px; font-weight: bold; text-align: center; color: {color}; margin: 20px 0; }}
            .btn {{ display: inline-block; background: linear-gradient(90deg, #7c3aed, #00d4ff); color: #fff; padding: 15px 30px; border-radius: 10px; text-decoration: none; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center; font-size: 28px; margin-bottom: 30px;">🚀 SSB Cloud</div>
            <h2>Subscription Expiring Soon</h2>
            <p>Your <strong>{plan}</strong> cloud subscription expires on:</p>
            <p style="font-size: 18px; color: #888;">{expires_at}</p>
            <div class="countdown">{days_left} Day{'s' if days_left != 1 else ''}</div>
            <p>Renew now to avoid interruption to your trading bot:</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="#" class="btn">Renew Subscription →</a>
            </div>
            <p style="color: #888; font-size: 14px;">
                After expiry, your bot will switch to DRY RUN mode and cloud panel access will be frozen.
            </p>
        </div>
    </body>
    </html>
    """
    
    return subject, html


def get_payment_failed_email(email: str, tx_hash: str, reason: str) -> tuple:
    """Payment verification failed"""
    subject = "❌ SSB Cloud - Payment Verification Failed"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .error-box {{ background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; border-radius: 10px; padding: 20px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center; font-size: 28px; margin-bottom: 30px;">🚀 SSB Cloud</div>
            <h2 style="color: #ef4444;">Payment Verification Failed</h2>
            <p>We could not verify your payment:</p>
            <div class="error-box">
                <p><strong>TX Hash:</strong> <code>{tx_hash[:30]}...</code></p>
                <p><strong>Reason:</strong> {reason}</p>
            </div>
            <p>Please ensure you:</p>
            <ul style="color: #888;">
                <li>Sent USDT on TRC20 network</li>
                <li>Sent the exact amount</li>
                <li>Used the correct wallet address</li>
            </ul>
            <p>If you believe this is an error, contact support with your TX hash.</p>
        </div>
    </body>
    </html>
    """
    
    return subject, html


def get_license_activated_email(email: str, token: str, plan: str, expires_at: str) -> tuple:
    """License activation confirmation"""
    subject = "🎉 SSB Cloud - License Activated!"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .token-box {{ background: #0f0c29; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0; }}
            .token {{ font-size: 18px; font-weight: bold; color: #00d4ff; font-family: monospace; word-break: break-all; }}
            .success {{ background: rgba(34, 197, 94, 0.2); border: 1px solid #22c55e; border-radius: 10px; padding: 15px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center; font-size: 28px; margin-bottom: 30px;">🚀 SSB Cloud</div>
            <div class="success">
                ✅ Your license has been successfully activated!
            </div>
            <h2>Welcome to {plan} Plan!</h2>
            <p>Your Cloud Access Token:</p>
            <div class="token-box">
                <div class="token">{token}</div>
            </div>
            <p><strong>Expires:</strong> {expires_at}</p>
            <p style="margin-top: 30px;">
                <a href="#" style="background: linear-gradient(90deg, #7c3aed, #00d4ff); color: #fff; padding: 15px 30px; border-radius: 10px; text-decoration: none; font-weight: 600;">
                    Login to Dashboard →
                </a>
            </p>
            <p style="color: #888; font-size: 14px; margin-top: 30px;">
                ⚠️ Keep your token secure! Do not share it with anyone.
            </p>
        </div>
    </body>
    </html>
    """
    
    return subject, html


# ============================================================
# EMAIL SENDING
# ============================================================

async def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via SMTP or print to console in dev mode"""
    
    if DEV_MODE or not SMTP_USER:
        # Development mode - print to console
        print(f"\n{'='*60}")
        print(f"📧 EMAIL (DEV MODE)")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"{'='*60}")
        # Extract visible text from HTML
        import re
        text = re.sub('<[^<]+?>', '', html_body)
        text = re.sub(r'\s+', ' ', text).strip()
        print(text[:500] + "..." if len(text) > 500 else text)
        print(f"{'='*60}\n")
        return True
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
        msg["To"] = to_email
        
        msg.attach(MIMEText(html_body, "html"))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        
        return True
        
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")
        return False


# ============================================================
# VERIFICATION CODE HELPERS
# ============================================================

def generate_verification_code() -> str:
    """Generate 6-digit verification code"""
    return ''.join(random.choices(string.digits, k=6))


def hash_code(code: str) -> str:
    """Hash verification code with SHA256"""
    return hashlib.sha256(code.encode()).hexdigest()


async def send_verification_email(email: str, code: str) -> bool:
    """Send verification code email"""
    subject, html = get_verification_code_email(code, email)
    return await send_email(email, subject, html)


async def send_suspension_email(email: str, reason: str) -> bool:
    """Send suspension notification"""
    subject, html = get_license_suspended_email(email, reason)
    return await send_email(email, subject, html)


async def send_expiry_reminder(email: str, days_left: int, plan: str, expires_at: str) -> bool:
    """Send expiry reminder"""
    subject, html = get_expiry_reminder_email(email, days_left, plan, expires_at)
    return await send_email(email, subject, html)


async def send_activation_email(email: str, token: str, plan: str, expires_at: str) -> bool:
    """Send license activation email"""
    subject, html = get_license_activated_email(email, token, plan, expires_at)
    return await send_email(email, subject, html)


async def send_payment_failed_email(email: str, tx_hash: str, reason: str) -> bool:
    """Send payment failure notification"""
    subject, html = get_payment_failed_email(email, tx_hash, reason)
    return await send_email(email, subject, html)


# ============================================================
# ADDITIONAL EMAIL TEMPLATES
# ============================================================

def get_payment_received_email(email: str, amount: float, plan: str, tx_hash: str) -> tuple:
    """Payment received confirmation"""
    subject = "✅ SSB Cloud - Payment Received!"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .success {{ background: rgba(34, 197, 94, 0.2); border: 1px solid #22c55e; border-radius: 10px; padding: 20px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center; font-size: 28px; margin-bottom: 30px;">🚀 SSB Cloud</div>
            <div class="success">✅ Payment of ${amount} USDT received!</div>
            <h2>Thank You!</h2>
            <p>Your payment has been confirmed:</p>
            <p><strong>Plan:</strong> {plan}</p>
            <p><strong>Amount:</strong> ${amount} USDT</p>
            <p style="font-size: 12px; color: #666;">TX: {tx_hash[:40]}...</p>
            <p>Your license will be activated shortly.</p>
        </div>
    </body>
    </html>
    """
    return subject, html


def get_device_change_alert_email(email: str, new_ip: str, new_device: str) -> tuple:
    """Device/IP change alert"""
    subject = "⚠️ SSB Cloud - New Device Detected"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .alert {{ background: rgba(245, 158, 11, 0.2); border: 1px solid #f59e0b; border-radius: 10px; padding: 20px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center; font-size: 28px; margin-bottom: 30px;">🚀 SSB Cloud</div>
            <h2 style="color: #f59e0b;">New Device Detected</h2>
            <p>A login attempt was made from a new device:</p>
            <div class="alert">
                <p><strong>IP Address:</strong> {new_ip}</p>
                <p><strong>Device ID:</strong> {new_device[:20]}...</p>
                <p><strong>Time:</strong> Just now</p>
            </div>
            <p>If this was you, no action is needed.</p>
            <p>If this was NOT you, please:</p>
            <ul style="color: #888;">
                <li>Contact support immediately</li>
                <li>Reset your access token</li>
            </ul>
        </div>
    </body>
    </html>
    """
    return subject, html


def get_instance_crash_email(email: str, error: str, restart_count: int) -> tuple:
    """Cloud instance crashed alert"""
    subject = "🔴 SSB Cloud - Instance Crashed"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .error {{ background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; border-radius: 10px; padding: 20px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center; font-size: 28px; margin-bottom: 30px;">🚀 SSB Cloud</div>
            <h2 style="color: #ef4444;">Trading Instance Crashed</h2>
            <p>Your cloud trading bot has stopped unexpectedly:</p>
            <div class="error">
                <p><strong>Error:</strong> {error}</p>
                <p><strong>Restart Attempts:</strong> {restart_count}/3</p>
            </div>
            <p>Please log into your dashboard to check the status.</p>
            <p style="margin-top: 20px;">
                <a href="#" style="background: linear-gradient(90deg, #7c3aed, #00d4ff); color: #fff; padding: 12px 25px; border-radius: 8px; text-decoration: none;">
                    View Dashboard →
                </a>
            </p>
        </div>
    </body>
    </html>
    """
    return subject, html


def get_license_renewed_email(email: str, plan: str, new_expiry: str, days_added: int) -> tuple:
    """License renewed confirmation"""
    subject = "🎉 SSB Cloud - Subscription Renewed!"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f0c29; color: #fff; padding: 40px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e, #16213e); border-radius: 15px; padding: 40px; }}
            .success {{ background: rgba(34, 197, 94, 0.2); border: 1px solid #22c55e; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center; font-size: 28px; margin-bottom: 30px;">🚀 SSB Cloud</div>
            <div class="success">
                <div style="font-size: 48px;">✅</div>
                <h2>Subscription Renewed!</h2>
            </div>
            <p><strong>Plan:</strong> {plan}</p>
            <p><strong>Days Added:</strong> +{days_added}</p>
            <p><strong>New Expiry:</strong> {new_expiry}</p>
            <p style="color: #888; margin-top: 20px;">Thank you for continuing with SSB Cloud!</p>
        </div>
    </body>
    </html>
    """
    return subject, html


# Additional send functions
async def send_payment_received_email(email: str, amount: float, plan: str, tx_hash: str) -> bool:
    """Send payment received confirmation"""
    subject, html = get_payment_received_email(email, amount, plan, tx_hash)
    return await send_email(email, subject, html)


async def send_device_alert_email(email: str, new_ip: str, new_device: str) -> bool:
    """Send device change alert"""
    subject, html = get_device_change_alert_email(email, new_ip, new_device)
    return await send_email(email, subject, html)


async def send_crash_alert_email(email: str, error: str, restart_count: int) -> bool:
    """Send instance crash alert"""
    subject, html = get_instance_crash_email(email, error, restart_count)
    return await send_email(email, subject, html)


async def send_renewal_email(email: str, plan: str, new_expiry: str, days_added: int) -> bool:
    """Send renewal confirmation"""
    subject, html = get_license_renewed_email(email, plan, new_expiry, days_added)
    return await send_email(email, subject, html)

