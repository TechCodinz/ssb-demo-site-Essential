"""
SSB PRO API - Email Service
Email sending for verification, license delivery, notifications
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from api.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html_content: str) -> bool:
    """Send an email"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, to, msg.as_string())
        
        logger.info(f"Email sent to {to}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


async def send_verification_email(email: str, token: str) -> bool:
    """Send email verification link"""
    verify_url = f"https://ssbpro.dev/verify?token={token}"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #0f172a; color: #f9fafb; padding: 40px;">
        <div style="max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 32px;">
            <h1 style="color: #22d3ee;">🎯 Verify Your Email</h1>
            <p>Welcome to Sol Sniper Bot PRO!</p>
            <p>Click the button below to verify your email address:</p>
            <a href="{verify_url}" style="display: inline-block; padding: 14px 28px; background: linear-gradient(135deg, #22d3ee, #a855f7); color: #0b1120; font-weight: bold; text-decoration: none; border-radius: 999px; margin: 20px 0;">
                ✅ Verify Email
            </a>
            <p style="color: #9ca3af; font-size: 12px;">If you didn't create an account, ignore this email.</p>
        </div>
    </body>
    </html>
    """
    
    return await send_email(email, "Verify Your SSB PRO Account", html)


async def send_license_email(email: str, license_key: str, plan: str) -> bool:
    """Send license key after successful payment"""
    dashboard_url = "https://app.ssbpro.dev/dashboard"
    download_url = "https://download.ssbpro.dev/latest"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #0f172a; color: #f9fafb; padding: 40px;">
        <div style="max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 32px;">
            <h1 style="color: #4ade80;">🎉 Your License is Ready!</h1>
            <p>Thank you for purchasing <strong>{plan.upper()}</strong>!</p>
            
            <div style="background: #0f172a; border: 1px solid #22d3ee; border-radius: 12px; padding: 20px; margin: 20px 0;">
                <p style="color: #9ca3af; margin: 0 0 8px;">Your License Key:</p>
                <p style="font-family: monospace; font-size: 18px; color: #22d3ee; margin: 0;">{license_key}</p>
            </div>
            
            <p><strong>Next Steps:</strong></p>
            <ol>
                <li>Download the bot from <a href="{download_url}" style="color: #22d3ee;">download.ssbpro.dev</a></li>
                <li>Run the installer</li>
                <li>Enter your license key when prompted</li>
                <li>Start trading!</li>
            </ol>
            
            <p>Or access your cloud dashboard:</p>
            <a href="{dashboard_url}" style="display: inline-block; padding: 12px 24px; background: linear-gradient(135deg, #22d3ee, #a855f7); color: #0b1120; font-weight: bold; text-decoration: none; border-radius: 999px;">
                🚀 Go to Dashboard
            </a>
            
            <p style="color: #9ca3af; font-size: 12px; margin-top: 30px;">
                Need help? Contact @SSB_Support on Telegram
            </p>
        </div>
    </body>
    </html>
    """
    
    return await send_email(email, f"🎯 Your SSB PRO License - {plan.upper()}", html)


async def send_renewal_reminder(email: str, days_left: int, plan: str) -> bool:
    """Send renewal reminder email"""
    renew_url = "https://ssbpro.dev/cloud#pricing"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #0f172a; color: #f9fafb; padding: 40px;">
        <div style="max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 32px;">
            <h1 style="color: #facc15;">⚠️ Subscription Expiring Soon</h1>
            <p>Your <strong>{plan.upper()}</strong> subscription expires in <strong>{days_left} days</strong>.</p>
            <p>Renew now to keep your cloud trading running:</p>
            <a href="{renew_url}" style="display: inline-block; padding: 14px 28px; background: linear-gradient(135deg, #22d3ee, #a855f7); color: #0b1120; font-weight: bold; text-decoration: none; border-radius: 999px; margin: 20px 0;">
                🔄 Renew Subscription
            </a>
        </div>
    </body>
    </html>
    """
    
    return await send_email(email, f"⚠️ SSB PRO Subscription Expiring in {days_left} Days", html)
