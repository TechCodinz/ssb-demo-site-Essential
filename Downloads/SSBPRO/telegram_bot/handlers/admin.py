"""
Sol Sniper Bot PRO - Admin Handler
Handles admin approve/reject and stats
"""
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.constants import ALL_PLANS, ADMIN_CHAT_ID, DOWNLOAD_LINKS
from utils.db import (
    get_order_by_ref, approve_order, reject_order,
    get_pending_orders, get_sales_stats, schedule_message
)
from utils.api_client import api_client
from messages.templates import (
    get_order_approved_message, ORDER_REJECTED_MESSAGE
)


def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    admin_ids = [int(ADMIN_CHAT_ID)]
    # Add more admin IDs here if needed
    return user_id in admin_ids


def generate_license_key(plan_id: str) -> str:
    """Generate a license key"""
    prefix_map = {
        "STANDARD": "SSB-STD",
        "PRO": "SSB-PRO",
        "ELITE": "SSB-ELITE",
        "CLOUD_STANDARD": "SSB-CLD-STD",
        "CLOUD_PRO": "SSB-CLD-PRO",
        "CLOUD_ELITE": "SSB-CLD-ELT",
    }
    prefix = prefix_map.get(plan_id, "SSB")
    part1 = random.randint(1000, 9999)
    part2 = random.randint(1000, 9999)
    return f"{prefix}-{part1}-{part2}"


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin approve/reject callbacks"""
    query = update.callback_query
    user = query.from_user
    
    if not is_admin(user.id):
        await query.answer("⛔ You are not authorized to perform this action.", show_alert=True)
        return
    
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("approve_"):
        order_ref = callback_data.replace("approve_", "")
        await process_approval(query, order_ref, user, context)
    
    elif callback_data.startswith("reject_"):
        order_ref = callback_data.replace("reject_", "")
        await process_rejection(query, order_ref, user, context)


async def process_approval(query, order_ref: str, admin_user, context) -> None:
    """Process order approval"""
    order = await get_order_by_ref(order_ref)
    
    if not order:
        await query.message.reply_text(f"❌ Order {order_ref} not found.")
        return
    
    if order["status"] != "pending":
        await query.message.reply_text(f"⚠️ Order {order_ref} already {order['status']}.")
        return
    
    plan_id = order["plan_id"]
    plan_info = ALL_PLANS.get(plan_id, {})
    
    # Generate license key
    license_key = generate_license_key(plan_id)
    
    # Try to activate via SaaS API (optional - may not be needed if local)
    license_type = "cloud" if "CLOUD" in plan_id else "desktop"
    api_result = await api_client.activate_license(
        email=order["email"],
        plan=plan_id,
        telegram_id=order["telegram_id"],
        order_id=order_ref,
        license_type=license_type
    )
    
    if api_result.get("ok"):
        license_key = api_result.get("license_key", license_key)
        dashboard_url = api_result.get("dashboard_url", "https://your-saas.com/dashboard")
    else:
        # Use local license if API fails
        dashboard_url = "https://your-saas.com/dashboard"
    
    # Update order in DB
    await approve_order(
        order_ref=order_ref,
        approved_by=admin_user.username or str(admin_user.id),
        license_key=license_key
    )
    
    # Get download link
    download_link = DOWNLOAD_LINKS.get(plan_id, "https://your-site.com/download")
    
    # Send license to buyer
    buyer_message = get_order_approved_message(
        plan_name=plan_info.get("name", plan_id),
        license_key=license_key,
        download_link=download_link,
        dashboard_url=dashboard_url
    )
    
    try:
        await context.bot.send_message(
            chat_id=int(order["telegram_id"]),
            text=buyer_message,
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.message.reply_text(f"⚠️ Could not message buyer: {e}")
    
    # Schedule marketing messages
    # Upsell in 24 hours
    await schedule_message(
        telegram_id=order["telegram_id"],
        message_type="upsell",
        scheduled_for=datetime.utcnow() + timedelta(hours=24)
    )
    
    # Review request in 48 hours
    await schedule_message(
        telegram_id=order["telegram_id"],
        message_type="review",
        scheduled_for=datetime.utcnow() + timedelta(hours=48)
    )
    
    # Update admin message
    await query.message.edit_text(
        query.message.text + f"\n\n✅ *APPROVED* by @{admin_user.username}\n🔑 `{license_key}`",
        parse_mode="Markdown"
    )


async def process_rejection(query, order_ref: str, admin_user, context) -> None:
    """Process order rejection"""
    order = await get_order_by_ref(order_ref)
    
    if not order:
        await query.message.reply_text(f"❌ Order {order_ref} not found.")
        return
    
    if order["status"] != "pending":
        await query.message.reply_text(f"⚠️ Order {order_ref} already {order['status']}.")
        return
    
    # Update order in DB
    await reject_order(
        order_ref=order_ref,
        rejected_by=admin_user.username or str(admin_user.id)
    )
    
    # Notify buyer
    try:
        await context.bot.send_message(
            chat_id=int(order["telegram_id"]),
            text=ORDER_REJECTED_MESSAGE,
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.message.reply_text(f"⚠️ Could not message buyer: {e}")
    
    # Update admin message
    await query.message.edit_text(
        query.message.text + f"\n\n❌ *REJECTED* by @{admin_user.username}",
        parse_mode="Markdown"
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /admin command - show admin menu"""
    user = update.message.from_user
    
    if not is_admin(user.id):
        await update.message.reply_text("⛔ You are not authorized.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📋 Pending Orders", callback_data="admin_pending")],
        [InlineKeyboardButton("📊 Sales Summary", callback_data="admin_stats")],
        [InlineKeyboardButton("🔑 Create Manual License", callback_data="admin_manual")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 *Admin Panel*\n\nSelect an option:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin menu callbacks"""
    query = update.callback_query
    user = query.from_user
    
    if not is_admin(user.id):
        await query.answer("⛔ Not authorized", show_alert=True)
        return
    
    await query.answer()
    
    if query.data == "admin_pending":
        await show_pending_orders(query)
    elif query.data == "admin_stats":
        await show_sales_stats(query)
    elif query.data == "admin_manual":
        await query.message.reply_text(
            "🔑 *Manual License Creation*\n\n"
            "Use format:\n"
            "/create_license EMAIL PLAN_ID\n\n"
            "Example:\n"
            "`/create_license buyer@email.com PRO`",
            parse_mode="Markdown"
        )


async def show_pending_orders(query) -> None:
    """Show pending orders"""
    orders = await get_pending_orders()
    
    if not orders:
        await query.message.reply_text("✅ No pending orders!")
        return
    
    message = "*📋 Pending Orders:*\n\n"
    for order in orders[:10]:
        message += (
            f"🆔 `{order['order_ref']}`\n"
            f"   Plan: {order['plan_id']}\n"
            f"   Amount: ${order['amount_usdt']}\n"
            f"   Email: {order['email']}\n"
            f"   TX: `{order['tx_hash'][:20] if order['tx_hash'] else 'N/A'}...`\n\n"
        )
    
    await query.message.reply_text(message, parse_mode="Markdown")


async def show_sales_stats(query) -> None:
    """Show sales statistics"""
    stats = await get_sales_stats()
    
    message = "*📊 Sales Summary*\n\n"
    message += f"💰 *Total Sales:* ${stats['total_sales_usdt']:.2f} USDT\n\n"
    
    message += "*Sales by Plan:*\n"
    for plan_id, data in stats.get("sales_by_plan", {}).items():
        message += f"• {plan_id}: {data['count']} orders (${data['total']:.2f})\n"
    
    message += "\n*Orders by Status:*\n"
    for status, count in stats.get("orders_by_status", {}).items():
        icon = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(status, "❓")
        message += f"{icon} {status}: {count}\n"
    
    await query.message.reply_text(message, parse_mode="Markdown")


async def create_license_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /create_license command"""
    user = update.message.from_user
    
    if not is_admin(user.id):
        await update.message.reply_text("⛔ You are not authorized.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /create_license EMAIL PLAN_ID\n"
            "Example: /create_license buyer@email.com PRO"
        )
        return
    
    email = args[0]
    plan_id = args[1].upper()
    
    if plan_id not in ALL_PLANS:
        await update.message.reply_text(
            f"❌ Invalid plan: {plan_id}\n"
            f"Valid plans: {', '.join(ALL_PLANS.keys())}"
        )
        return
    
    license_key = generate_license_key(plan_id)
    
    await update.message.reply_text(
        f"✅ *License Created*\n\n"
        f"📧 Email: `{email}`\n"
        f"📦 Plan: {plan_id}\n"
        f"🔑 Key: `{license_key}`",
        parse_mode="Markdown"
    )
