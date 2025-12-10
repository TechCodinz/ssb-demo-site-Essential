"""
Sol Sniper Bot PRO - Telegram Order Bot
Main entry point

Usage:
    python bot.py

Environment Variables:
    TELEGRAM_BOT_TOKEN - Bot token from @BotFather
    TELEGRAM_ADMIN_CHAT_ID - Admin chat/group ID
    USDT_WALLET_ADDRESS - Your USDT TRC20 address
"""
import asyncio
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# Import from local modules (non-relative now)
from utils.constants import BOT_TOKEN, STATE_SELECT_PLAN, STATE_CONFIRM_PLAN, STATE_ENTER_TX, STATE_ENTER_EMAIL, STATE_ENTER_NOTE
from utils.db import init_db
from handlers.start import start, plan_selected, help_command, copy_wallet_handler
from handlers.order import (
    payment_confirmed, tx_hash_received, email_received,
    note_received, handle_web_order, check_status
)
from handlers.admin import (
    handle_admin_callback, admin_command, admin_menu_callback,
    create_license_command
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def cancel(update: Update, context) -> int:
    """Cancel the current conversation"""
    await update.message.reply_text(
        "❌ Operation cancelled.\n\nUse /start to begin again."
    )
    return ConversationHandler.END


def main():
    """Start the bot"""
    logger.info("🚀 Starting Sol Sniper Bot PRO - Order Bot")
    
    # Build application
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Main conversation handler for order flow
    order_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🧾 New SSB Order"), handle_web_order),
        ],
        states={
            STATE_SELECT_PLAN: [
                CallbackQueryHandler(plan_selected, pattern="^plan_"),
                CallbackQueryHandler(plan_selected, pattern="^help$"),
                CallbackQueryHandler(plan_selected, pattern="^back_to_plans$"),
            ],
            STATE_CONFIRM_PLAN: [
                CallbackQueryHandler(payment_confirmed, pattern="^paid$"),
                CallbackQueryHandler(copy_wallet_handler, pattern="^copy_wallet$"),
                CallbackQueryHandler(plan_selected, pattern="^back_to_plans$"),
            ],
            STATE_ENTER_TX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tx_hash_received),
            ],
            STATE_ENTER_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, email_received),
            ],
            STATE_ENTER_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, note_received),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
    )
    
    # Register handlers
    app.add_handler(order_conv)
    
    # Admin commands
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("create_license", create_license_command))
    
    # Admin callbacks (approve/reject)
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^reject_"))
    app.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin_"))
    
    # Utility commands
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", check_status))
    
    # Web order handler (for messages starting with specific format)
    app.add_handler(MessageHandler(
        filters.Regex(r"(?i)(plan:|tx hash:|email:)"),
        handle_web_order
    ))
    
    logger.info("✅ Bot handlers registered")
    logger.info("📡 Starting polling...")
    
    # Run the bot
    app.run_polling(drop_pending_updates=True)


async def startup():
    """Async startup tasks"""
    await init_db()
    logger.info("✅ Database initialized")


if __name__ == "__main__":
    # Initialize database first
    asyncio.run(startup())
    
    # Start bot
    main()
