"""
Sol Sniper Bot PRO - Order Handler
Handles order creation and TX hash submission
"""
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from utils.constants import (
    ALL_PLANS, ADMIN_CHAT_ID,
    STATE_ENTER_EMAIL, STATE_ENTER_TX, STATE_ENTER_NOTE
)
from utils.db import create_order, update_order_tx, get_order_by_ref
from messages.templates import (
    TX_HASH_REQUEST, EMAIL_REQUEST,
    get_order_received_message, get_admin_order_alert
)


async def payment_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User clicked 'I Have Paid' - ask for TX hash"""
    query = update.callback_query
    await query.answer()
    
    if "selected_plan" not in context.user_data:
        await query.message.reply_text("Please select a plan first using /start")
        return ConversationHandler.END
    
    await query.message.reply_text(
        TX_HASH_REQUEST,
        parse_mode="Markdown"
    )
    
    return STATE_ENTER_TX


async def tx_hash_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle TX hash submission"""
    tx_hash = update.message.text.strip()
    
    # Basic TX hash validation (Tron TX hashes are 64 hex chars)
    if len(tx_hash) < 30:
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid TX hash.\n"
            "Please paste the full transaction ID from TronScan."
        )
        return STATE_ENTER_TX
    
    context.user_data["tx_hash"] = tx_hash
    
    await update.message.reply_text(
        EMAIL_REQUEST,
        parse_mode="Markdown"
    )
    
    return STATE_ENTER_EMAIL


async def email_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle email submission"""
    email = update.message.text.strip().lower()
    
    # Basic email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        await update.message.reply_text(
            "⚠️ Please enter a valid email address."
        )
        return STATE_ENTER_EMAIL
    
    context.user_data["email"] = email
    
    await update.message.reply_text(
        "📝 *Optional:* Add a note (Telegram handle, referral, HWID, etc.)\n\n"
        "If nothing to add, type `-`",
        parse_mode="Markdown"
    )
    
    return STATE_ENTER_NOTE


async def note_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle note submission and create order"""
    note = update.message.text.strip()
    if note == "-":
        note = ""
    
    context.user_data["note"] = note
    
    # Get all collected data
    user = update.message.from_user
    plan_id = context.user_data.get("selected_plan")
    plan_info = context.user_data.get("plan_info", {})
    tx_hash = context.user_data.get("tx_hash", "")
    email = context.user_data.get("email", "")
    
    # Create order in database
    order = await create_order(
        telegram_id=str(user.id),
        telegram_username=user.username,
        email=email,
        plan_id=plan_id,
        plan_type=plan_info.get("type", "desktop"),
        amount_usdt=plan_info.get("price", 0),
        tx_hash=tx_hash,
        note=note
    )
    
    # Send confirmation to user
    await update.message.reply_text(
        get_order_received_message(
            plan=plan_info.get("name", plan_id),
            email=email,
            tx_hash=tx_hash,
            order_id=order["order_ref"]
        ),
        parse_mode="Markdown"
    )
    
    # Send alert to admin with approve/reject buttons
    admin_keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order['order_ref']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order['order_ref']}"),
        ],
        [
            InlineKeyboardButton("🔍 Check TX on TronScan", url=f"https://tronscan.org/#/transaction/{tx_hash}")
        ]
    ]
    admin_markup = InlineKeyboardMarkup(admin_keyboard)
    
    admin_msg = get_admin_order_alert(
        username=user.username,
        user_id=user.id,
        plan=plan_info.get("name", plan_id),
        price=plan_info.get("price", 0),
        email=email,
        tx_hash=tx_hash,
        order_id=order["order_ref"],
        note=note
    )
    
    await update.get_bot().send_message(
        chat_id=ADMIN_CHAT_ID,
        text=admin_msg,
        parse_mode="Markdown",
        reply_markup=admin_markup
    )
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END


async def handle_web_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle orders sent from website in the format:
    
    🧾 New SSB Order
    Plan: PRO (LIVE)
    TX Hash: 4839bcdbe1a9ec...
    Email: buyer@example.com
    Note: @username
    """
    text = update.message.text
    user = update.message.from_user
    
    # Parse the message
    lines = text.strip().split("\n")
    order_data = {}
    
    for line in lines:
        if "Plan:" in line:
            order_data["plan"] = line.split("Plan:")[1].strip()
        elif "TX Hash:" in line or "TX:" in line:
            parts = line.split(":")
            order_data["tx_hash"] = parts[-1].strip()
        elif "Email:" in line:
            order_data["email"] = line.split("Email:")[1].strip()
        elif "Note:" in line:
            order_data["note"] = line.split("Note:")[1].strip()
    
    # Map plan name to plan_id
    plan_map = {
        "STANDARD": "STANDARD",
        "PRO": "PRO",
        "ELITE": "ELITE",
        "CLOUD STANDARD": "CLOUD_STANDARD",
        "CLOUD PRO": "CLOUD_PRO",
        "CLOUD ELITE": "CLOUD_ELITE",
    }
    
    plan_text = order_data.get("plan", "").upper()
    plan_id = None
    for key, val in plan_map.items():
        if key in plan_text:
            plan_id = val
            break
    
    if not plan_id:
        plan_id = "PRO"  # Default
    
    plan_info = ALL_PLANS.get(plan_id, ALL_PLANS["PRO"])
    
    # Create order
    order = await create_order(
        telegram_id=str(user.id),
        telegram_username=user.username,
        email=order_data.get("email", "unknown@email.com"),
        plan_id=plan_id,
        plan_type=plan_info.get("type", "desktop"),
        amount_usdt=plan_info.get("price", 0),
        tx_hash=order_data.get("tx_hash", ""),
        note=order_data.get("note", "")
    )
    
    # Reply to buyer
    await update.message.reply_text(
        get_order_received_message(
            plan=plan_info.get("name", plan_id),
            email=order_data.get("email", ""),
            tx_hash=order_data.get("tx_hash", ""),
            order_id=order["order_ref"]
        ),
        parse_mode="Markdown"
    )
    
    # Admin alert
    admin_keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order['order_ref']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order['order_ref']}"),
        ],
        [
            InlineKeyboardButton("🔍 Check TX", url=f"https://tronscan.org/#/transaction/{order_data.get('tx_hash', '')}")
        ]
    ]
    admin_markup = InlineKeyboardMarkup(admin_keyboard)
    
    admin_msg = get_admin_order_alert(
        username=user.username,
        user_id=user.id,
        plan=plan_info.get("name", plan_id),
        price=plan_info.get("price", 0),
        email=order_data.get("email", ""),
        tx_hash=order_data.get("tx_hash", ""),
        order_id=order["order_ref"],
        note=order_data.get("note", "")
    )
    
    await update.get_bot().send_message(
        chat_id=ADMIN_CHAT_ID,
        text=admin_msg,
        parse_mode="Markdown",
        reply_markup=admin_markup
    )
    
    return ConversationHandler.END


async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - show user's orders"""
    from utils.db import get_orders_by_telegram_id
    
    user_id = str(update.message.from_user.id)
    orders = await get_orders_by_telegram_id(user_id)
    
    if not orders:
        await update.message.reply_text(
            "📋 You have no orders yet.\n\n"
            "Use /start to purchase a plan!"
        )
        return
    
    status_icons = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌",
    }
    
    message = "*📋 Your Orders:*\n\n"
    for order in orders[:5]:  # Show last 5
        icon = status_icons.get(order["status"], "❓")
        message += (
            f"{icon} *{order['order_ref']}*\n"
            f"   Plan: {order['plan_id']}\n"
            f"   Status: {order['status'].upper()}\n"
            f"   Date: {order['created_at'][:10]}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode="Markdown")
