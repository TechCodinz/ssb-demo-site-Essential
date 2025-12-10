"""
Sol Sniper Bot PRO - Premium Message Templates
Ultra-premium marketing messages that build trust and drive conversions.
"""

from utils.constants import USDT_WALLET, USDT_NETWORK, SUPPORT_USERNAME


# ============================================================
# PREMIUM WELCOME MESSAGE
# ============================================================

WELCOME_MESSAGE = """
╔══════════════════════════════════════╗
║    🚀 *SOL SNIPER BOT PRO* 🚀         ║
║    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    ║
║    _The #1 Solana Trading Bot_        ║
╚══════════════════════════════════════╝

⚡ *AI-Powered* • *Ultra-Fast* • *Profitable*

Trusted by *2,000+* traders worldwide 🌍
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💎 *LIFETIME DESKTOP LICENSES*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟪 *STANDARD* — `$199`
├ ✓ Full GUI + Source Code
├ ✓ DRY RUN Mode
└ ✓ Community Support

🟦 *PRO* — `$499` ⭐ _POPULAR_
├ ✓ Everything in STANDARD
├ ✓ LIVE Trading Enabled
├ ✓ Advanced Filters
└ ✓ Priority Support

🟩 *ELITE* — `$899` 👑 _BEST VALUE_
├ ✓ Everything in PRO
├ ✓ Ultra-Fast Engine (0.3s)
├ ✓ Lifetime Updates
├ ✓ VIP Discord Access
└ ✓ 1-on-1 Setup Call

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

☁️ *CLOUD SNIPER* (24/7 Automated)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

☁️ *CLOUD SNIPER* — `$79/mo`
├ ✓ 24/7 Cloud Bot
├ ✓ Full AI Analysis
└ ✓ Dashboard + Alerts

☁️ *CLOUD SNIPER PRO* — `$149/mo` ⭐
├ ✓ Everything in SNIPER
├ ✓ LIVE Trading
└ ✓ Priority Execution

☁️ *CLOUD SNIPER ELITE* — `$249/mo` 👑
├ ✓ Everything in PRO
├ ✓ Ultra-Fast Engine
└ ✓ Divine Features

_No PC needed — bot runs 24/7 on our servers!_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ *Why Choose SSB PRO?*

✅ 5-Star Reviews on Telegram
✅ 48h Average Delivery
✅ Active Development Team
✅ Real Profits (Check #profits channel)
✅ 30-Day Money Back Guarantee*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 *Select Your Plan Below* 👇
"""


# ============================================================
# PLAN SELECTED - PREMIUM PAYMENT SCREEN
# ============================================================

def get_plan_selected_message(plan_name: str, price: float, plan_type: str) -> str:
    billing = "/month" if plan_type == "cloud" else " ONE-TIME"
    
    # Different badges for different plans
    badges = {
        "STANDARD": "🟪",
        "PRO": "🟦 ⭐",
        "ELITE": "🟩 👑",
        "CLOUD STANDARD": "☁️",
        "CLOUD PRO": "☁️ ⭐",
        "CLOUD ELITE": "☁️ 👑"
    }
    badge = badges.get(plan_name.upper(), "💎")
    
    return f"""
╔══════════════════════════════════════╗
║  ✅ *ORDER: {plan_name}*              
║  {badge}                              
╚══════════════════════════════════════╝

💰 *Total:* `${price:.0f}` USDT{billing}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *SECURE PAYMENT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 *Network:* TRON (TRC20)
🛡️ *Status:* Verified Wallet

📍 *Send USDT Here:*
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ `{USDT_WALLET}` ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

☝️ _Tap address to copy_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ *IMPORTANT INSTRUCTIONS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 Send *EXACTLY* `${price:.0f} USDT`
📌 Use *TRC20 Network* Only
📌 Double-check wallet address
📌 Save your TX Hash after payment

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *What Happens Next?*

1️⃣ Send payment to wallet above
2️⃣ Click "I Have Paid" below
3️⃣ Enter your TX Hash
4️⃣ Receive license in ~5 minutes!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def get_payment_qr_message(plan_name: str, price: float) -> str:
    """Message to send with QR code image"""
    return f"""
╔══════════════════════════════════════╗
║   📱 *SCAN TO PAY*                    ║
║   {plan_name} — ${price:.0f} USDT      ║
╚══════════════════════════════════════╝

🔗 *Network:* TRC20 (TRON)

📍 *Wallet Address:*
`{USDT_WALLET}`

☝️ _Tap to copy • Scan QR above_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ *Secure Payment* • *Instant Verification*
"""


# ============================================================
# TX HASH REQUEST - PREMIUM
# ============================================================

TX_HASH_REQUEST = """
╔══════════════════════════════════════╗
║   📝 *ENTER TRANSACTION HASH*        ║
╚══════════════════════════════════════╝

Please paste your *TX Hash* (Transaction ID)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 *How to find your TX Hash:*

1️⃣ Open TronLink or your wallet app
2️⃣ Find the USDT transfer you just sent
3️⃣ Copy the Transaction ID / Hash

_Example:_ `7cbd98e91a9f2abc123...`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 *Paste your TX Hash below:*
"""


# ============================================================
# EMAIL REQUEST - PREMIUM
# ============================================================

EMAIL_REQUEST = """
╔══════════════════════════════════════╗
║   📧 *ENTER YOUR EMAIL*              ║
╚══════════════════════════════════════╝

Your license key and download link will be sent to this email.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Use a valid email you can access
✅ Check spam folder if not received
✅ Gmail / Outlook recommended

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 *Enter your email:*
"""


# ============================================================
# ORDER RECEIVED - PREMIUM
# ============================================================

def get_order_received_message(plan: str, email: str, tx_hash: str, order_id: str) -> str:
    return f"""
╔══════════════════════════════════════╗
║   🎉 *ORDER RECEIVED!*               ║
║   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║   Thank You for Your Purchase! 🚀    ║
╚══════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 *Order Details*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🆔 *Order ID:* `{order_id}`
📦 *Plan:* {plan}
📧 *Email:* `{email}`
🔗 *TX:* `{tx_hash[:24]}...`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏳ *Verification Status*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟡 *Processing...* (Usually 3-8 minutes)

Our system is verifying your payment.
You'll be notified here once approved!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 *What You'll Receive:*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ License Key
✅ Download Link (Desktop)
✅ Dashboard Access (Cloud)
✅ Setup Guide

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_Questions? Contact @{SUPPORT_USERNAME}_
"""


# ============================================================
# ORDER APPROVED - LICENSE DELIVERY
# ============================================================

def get_order_approved_message(
    plan_name: str, 
    license_key: str, 
    download_link: str, 
    dashboard_url: str
) -> str:
    return f"""
╔══════════════════════════════════════╗
║   🎉 *LICENSE ACTIVATED!* 🎉         ║
║   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║   Welcome to Sol Sniper Bot PRO!     ║
╚══════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 *Your Plan:* {plan_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 *LICENSE KEY:*
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ `{license_key}` ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

_☝️ Tap to copy • Save this key!_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 *DOWNLOADS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 *Bot Bundle:* [Download Here]({download_link})
🌐 *Dashboard:* [Open Dashboard]({dashboard_url})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 *QUICK START GUIDE*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ Download & Extract the bundle
2️⃣ Run install\\_dependencies.bat
3️⃣ Enter your License Key
4️⃣ Start sniping! 🎯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Need Help?*

📞 Support: @{SUPPORT_USERNAME}
📖 Docs: See included README

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 *Welcome to the SSB Family!*
_Time to dominate the Solana markets!_ 🚀
"""


# ============================================================
# ORDER REJECTED - PREMIUM
# ============================================================

ORDER_REJECTED_MESSAGE = f"""
╔══════════════════════════════════════╗
║   ❌ *PAYMENT NOT VERIFIED*          ║
╚══════════════════════════════════════╝

We couldn't verify your transaction.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❓ *Common Issues:*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Wrong network (must be TRC20)
• Incorrect amount sent
• Invalid TX hash
• Transaction still pending

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 *What To Do:*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ Double-check your TX on TronScan
2️⃣ Ensure payment is confirmed
3️⃣ Re-submit your TX hash

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📞 *Need Help?* Contact @{SUPPORT_USERNAME}

_We're here 24/7 to assist you!_
"""


# ============================================================
# ADMIN NOTIFICATION - NEW ORDER
# ============================================================

def get_admin_order_alert(
    username: str,
    user_id: int,
    plan: str,
    price: float,
    email: str,
    tx_hash: str,
    order_id: str,
    note: str = ""
) -> str:
    return f"""
🚨 *NEW ORDER ALERT* 🚨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 *Customer:* @{username or 'N/A'}
🆔 *Telegram ID:* `{user_id}`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 *Plan:* {plan}
💰 *Amount:* ${price:.0f} USDT
📧 *Email:* `{email}`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 *TX Hash:*
`{tx_hash}`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 *Note:* {note or '(none)'}
🆔 *Order:* `{order_id}`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⬇️ *Verify TX and take action:*
"""


# ============================================================
# UPSELL MESSAGE
# ============================================================

UPSELL_MESSAGE = """
╔══════════════════════════════════════╗
║   🔥 *UPGRADE YOUR PLAN!* 🔥         ║
╚══════════════════════════════════════╝

Your bot is now *ACTIVE* — but you could be making MORE! 💰

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👑 *UPGRADE TO ELITE — Unlock:*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ *Ultra-Fast Engine* (0.3s entries)
🛡️ *Advanced Honeypot Shield*
🔮 *Early-Entry Detection*
☁️ *Cloud Auto-Trading*
🎯 *99.2% Win Rate Signals*
📞 *1-on-1 Setup Call*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💸 *LIMITED OFFER:* Reply *UPGRADE* 
to get *$100 OFF* today!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


# ============================================================
# REVIEW REQUEST
# ============================================================

REVIEW_REQUEST_MESSAGE = """
╔══════════════════════════════════════╗
║   ⭐ *ENJOYING SSB PRO?* ⭐          ║
╚══════════════════════════════════════╝

Hey! Hope your trading journey has been *profitable*! 📈

If you're happy with the results, we'd love a quick review! 

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎁 *Leave a review and get:*
• Early access to new features
• Priority support  
• Exclusive Discord role

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reply *REVIEW* to share your experience!

_Thank you for being part of the SSB family!_ 🚀
"""


# ============================================================
# RENEWAL REMINDER
# ============================================================

def get_renewal_reminder(plan_name: str, expires_date: str, price: float) -> str:
    return f"""
╔══════════════════════════════════════╗
║   ⏰ *SUBSCRIPTION EXPIRING!*        ║
╚══════════════════════════════════════╝

Your *{plan_name}* subscription expires:
📅 *{expires_date}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 *Renew Now:* ${price:.0f} USDT

Send payment to continue trading 24/7!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎁 *Renew early and get:*
• +3 bonus days FREE
• Priority queue access

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_Don't miss profitable trades!_ 📈
"""


# ============================================================
# CLOUD EXPIRED
# ============================================================

CLOUD_EXPIRED_MESSAGE = """
╔══════════════════════════════════════╗
║   ⚠️ *SUBSCRIPTION EXPIRED*         ║
╚══════════════════════════════════════╝

Your cloud trading bot has been *paused*.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📉 *While you were away:*
• 47 potential trades missed
• Estimated profit: $2,340

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *Reactivate now to:*

✅ Resume 24/7 auto-trading
✅ Catch the next pump
✅ Keep making passive income

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 *Select a plan below to renew:*
"""
