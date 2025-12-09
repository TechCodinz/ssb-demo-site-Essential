"""
Sol Sniper Bot PRO - Start Handler
Handles /start command and premium plan selection with QR code
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from utils.constants import (
    DESKTOP_PLANS, CLOUD_PLANS, ALL_PLANS,
    STATE_SELECT_PLAN, STATE_CONFIRM_PLAN, USDT_WALLET
)
from messages.templates import WELCOME_MESSAGE, get_plan_selected_message, get_payment_qr_message


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command - show premium welcome with plan buttons"""
    
    # Build premium keyboard with emojis and badges
    keyboard = [
        # Header row
        [
            InlineKeyboardButton("━━━ 💎 LIFETIME LICENSES 💎 ━━━", callback_data="header_lifetime"),
        ],
        # Desktop plans
        [
            InlineKeyboardButton("🟪 STANDARD — $199", callback_data="plan_STANDARD"),
        ],
        [
            InlineKeyboardButton("🟦 PRO — $499 ⭐ POPULAR", callback_data="plan_PRO"),
        ],
        [
            InlineKeyboardButton("🟩 ELITE — $899 👑 BEST", callback_data="plan_ELITE"),
        ],
        # Divider
        [
            InlineKeyboardButton("━━━ ☁️ CLOUD TRADING ☁️ ━━━", callback_data="header_cloud"),
        ],
        # Cloud plans
        [
            InlineKeyboardButton("☁️ CLOUD SNIPER — $79/mo", callback_data="plan_CLOUD_SNIPER"),
        ],
        [
            InlineKeyboardButton("☁️ CLOUD SNIPER PRO — $149/mo ⭐", callback_data="plan_CLOUD_SNIPER_PRO"),
        ],
        [
            InlineKeyboardButton("☁️ CLOUD SNIPER ELITE — $249/mo 👑", callback_data="plan_CLOUD_SNIPER_ELITE"),
        ],
        # Footer
        [
            InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━", callback_data="divider"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
            InlineKeyboardButton("🌐 Website", url="https://solsniperbot.pro"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            WELCOME_MESSAGE,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            WELCOME_MESSAGE,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    return STATE_SELECT_PLAN


async def plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle plan selection callback - show payment with QR code"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Ignore header/divider clicks
    if callback_data in ["header_lifetime", "header_cloud", "divider"]:
        return STATE_SELECT_PLAN
    
    if callback_data == "help":
        help_msg = """
╔══════════════════════════════════════╗
║   📞 *SUPPORT CENTER*                ║
╚══════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📞 *Contact:* @SSB_Support
⏰ *Hours:* 24/7 Available
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❓ *FAQs:*

• *Payment not verified?*
  Wait 5 mins, then contact support

• *Need HWID reset?*
  Message support with your license

• *Technical issues?*
  Join our Discord for instant help

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_Use /start to view plans again_
"""
        await query.message.reply_text(help_msg, parse_mode="Markdown")
        return STATE_SELECT_PLAN
    
    if callback_data == "back_to_plans":
        return await start(update, context)
    
    # Extract plan ID from callback
    if callback_data.startswith("plan_"):
        plan_id = callback_data.replace("plan_", "")
        
        if plan_id not in ALL_PLANS:
            await query.message.reply_text("Invalid plan. Please try again.")
            return await start(update, context)
        
        plan = ALL_PLANS[plan_id]
        context.user_data["selected_plan"] = plan_id
        context.user_data["plan_info"] = plan
        
        # Generate and send QR code first
        try:
            import qrcode
            from io import BytesIO
            
            # Create premium QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=12,
                border=3,
            )
            qr.add_data(USDT_WALLET)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="#1a1a2e", back_color="white")
            
            # Save to bytes
            bio = BytesIO()
            bio.name = 'payment_qr.png'
            img.save(bio, 'PNG')
            bio.seek(0)
            
            # Premium QR caption
            qr_caption = get_payment_qr_message(plan["name"], plan["price"])
            
            await query.message.reply_photo(
                photo=bio,
                caption=qr_caption,
                parse_mode="Markdown"
            )
            
        except ImportError:
            # QR library not installed - skip
            pass
        except Exception as e:
            print(f"QR generation error: {e}")
        
        # Show plan confirmation with payment instructions
        message = get_plan_selected_message(
            plan_name=plan["name"],
            price=plan["price"],
            plan_type=plan["type"]
        )
        
        # Add features list
        features_list = "\n".join([f"✓ {f}" for f in plan["features"]])
        message += f"\n*📋 What You Get:*\n{features_list}"
        
        # Premium buttons
        keyboard = [
            [
                InlineKeyboardButton("📋 Copy Wallet", callback_data="copy_wallet"),
                InlineKeyboardButton("🔍 Check TX", url=f"https://tronscan.org/#/address/{USDT_WALLET}"),
            ],
            [
                InlineKeyboardButton("✅ I HAVE PAID", callback_data="paid"),
            ],
            [
                InlineKeyboardButton("◀️ Back to Plans", callback_data="back_to_plans"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        return STATE_CONFIRM_PLAN
    
    return STATE_SELECT_PLAN


async def copy_wallet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle copy wallet button - resend wallet address in easy copy format"""
    query = update.callback_query
    await query.answer("✅ Wallet address shown below!")
    
    wallet_msg = f"""
╔══════════════════════════════════════╗
║   📍 *PAYMENT WALLET*                ║
╚══════════════════════════════════════╝

🔗 *Network:* TRC20 (TRON)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

`{USDT_WALLET}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

☝️ *Tap the address above to copy*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ *Verified SSB Official Wallet*
"""
    
    await query.message.reply_text(
        wallet_msg,
        parse_mode="Markdown"
    )
    
    return STATE_CONFIRM_PLAN


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    help_text = """
╔══════════════════════════════════════╗
║   🆘 *SOL SNIPER BOT PRO - HELP*    ║
╚══════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 *COMMANDS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/start — View plans & purchase
/order — Submit a new order
/status — Check order status
/help — Show this message

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💳 *PAYMENT INFO*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• We accept *USDT (TRC20)* only
• Send exact amount shown
• Click "I Have Paid" after sending
• Delivery: ~5 minutes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📞 *SUPPORT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@SSB_Support — 24/7 Available

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_Use /start to begin your order!_
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")
