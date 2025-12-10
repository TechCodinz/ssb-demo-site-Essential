"""
Sol Sniper Bot PRO - Telegram Order Bot Constants
Complete pricing, plans, and configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# BOT CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8580154212:AAEunDZLqIFy9f6NarQdewIqtjm_aI7CIL8")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "5329503447")
SUPPORT_USERNAME = os.getenv("TELEGRAM_SUPPORT_USERNAME", "SSB_Support")

# USDT TRC20 Payment
USDT_WALLET = os.getenv("USDT_WALLET_ADDRESS", "TBxck6t1a3pZE2YLho4Su1PcGKd2yK2zD4")
USDT_NETWORK = "TRC20"

# SaaS API
SAAS_API_URL = os.getenv("SAAS_API_URL", "http://localhost:8000")
SAAS_API_KEY = os.getenv("SAAS_API_KEY", "")

# ============================================================
# PRICING - DESKTOP (ONE-TIME)
# ============================================================

DESKTOP_PLANS = {
    "STANDARD": {
        "name": "STANDARD – DRY RUN",
        "price": 199.0,
        "tier": "STANDARD",
        "type": "desktop",
        "features": [
            "✅ Full GUI Bot",
            "✅ DRY RUN Mode Only",
            "✅ Python Source Code",
            "✅ Free Updates",
            "❌ No LIVE Trading",
        ]
    },
    "PRO": {
        "name": "PRO – LIVE TRADING",
        "price": 499.0,
        "tier": "PRO",
        "type": "desktop",
        "features": [
            "✅ Full GUI Bot",
            "✅ DRY RUN + LIVE Mode",
            "✅ Python Source Code",
            "✅ Free Updates",
            "✅ Priority Support",
        ]
    },
    "ELITE": {
        "name": "ELITE – LIFETIME",
        "price": 899.0,
        "tier": "ELITE",
        "type": "desktop",
        "features": [
            "✅ Full GUI Bot",
            "✅ DRY RUN + LIVE Mode",
            "✅ Python Source Code",
            "✅ Lifetime Updates",
            "✅ VIP Support",
            "✅ Ultra-Fast Engine",
        ]
    },
}

# ============================================================
# PRICING - CLOUD (MONTHLY SUBSCRIPTION)
# ============================================================

CLOUD_PLANS = {
    "CLOUD_SNIPER": {
        "name": "CLOUD SNIPER",
        "price": 79.0,
        "tier": "STANDARD",
        "type": "cloud",
        "billing": "monthly",
        "features": [
            "☁️ 24/7 Cloud Bot",
            "✅ Full AI Analysis",
            "✅ Dashboard Access",
            "✅ Telegram Alerts",
            "✅ DRY RUN Mode",
        ]
    },
    "CLOUD_SNIPER_PRO": {
        "name": "CLOUD SNIPER PRO",
        "price": 149.0,
        "tier": "PRO",
        "type": "cloud",
        "billing": "monthly",
        "features": [
            "☁️ 24/7 Cloud Bot",
            "✅ DRY RUN + LIVE Mode",
            "✅ Dashboard Access",
            "✅ Telegram Alerts",
            "✅ Priority Execution",
            "✅ Advanced Filters",
        ]
    },
    "CLOUD_SNIPER_ELITE": {
        "name": "CLOUD SNIPER ELITE",
        "price": 249.0,
        "tier": "ELITE",
        "type": "cloud",
        "billing": "monthly",
        "features": [
            "☁️ 24/7 Cloud Bot",
            "✅ DRY RUN + LIVE Mode",
            "✅ Dashboard Access",
            "✅ Telegram Alerts",
            "✅ Ultra-Fast Engine",
            "✅ VIP Support",
            "✅ Divine Features",
        ]
    },
}

# ============================================================
# CREDIT PACKS (BONUS OPTION)
# ============================================================

CREDIT_PACKS = {
    "10_DAYS": {
        "name": "10 Trading Days",
        "price": 10.0,
        "days": 10,
    },
    "30_DAYS": {
        "name": "30 Trading Days",
        "price": 25.0,
        "days": 30,
    },
    "120_DAYS": {
        "name": "4 Months Trading",
        "price": 100.0,
        "days": 120,
    },
}

# ============================================================
# ALL PLANS COMBINED
# ============================================================

ALL_PLANS = {**DESKTOP_PLANS, **CLOUD_PLANS}

# ============================================================
# DOWNLOAD LINKS (Configure these!)
# ============================================================

DOWNLOAD_LINKS = {
    "STANDARD": os.getenv("DOWNLOAD_LINK_STANDARD", "https://your-site.com/download/standard"),
    "PRO": os.getenv("DOWNLOAD_LINK_PRO", "https://your-site.com/download/pro"),
    "ELITE": os.getenv("DOWNLOAD_LINK_ELITE", "https://your-site.com/download/elite"),
    "CLOUD_STANDARD": os.getenv("DOWNLOAD_LINK_CLOUD", "https://your-site.com/dashboard"),
    "CLOUD_PRO": os.getenv("DOWNLOAD_LINK_CLOUD", "https://your-site.com/dashboard"),
    "CLOUD_ELITE": os.getenv("DOWNLOAD_LINK_CLOUD", "https://your-site.com/dashboard"),
}

# ============================================================
# CONVERSATION STATES
# ============================================================

(
    STATE_SELECT_PLAN,
    STATE_CONFIRM_PLAN,
    STATE_ENTER_EMAIL,
    STATE_ENTER_TX,
    STATE_ENTER_NOTE,
    STATE_ADMIN_ACTION,
) = range(6)
