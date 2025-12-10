import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ==== CONFIG ====
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
ADMIN_CHAT_ID = 123456789   # your Telegram numeric ID
USDT_ADDRESS = "TBxck6t1a3pZE2YLho4Su1PcGKd2yK2zD4"

PLAN, TXHASH, EMAIL, NOTE = range(4)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🚀 Welcome to *Sol Sniper Bot PRO* order bot.\n\n"
        "We only accept *USDT (TRC20)*.\n\n"
        "*Prices:*\n"
        "• STANDARD – 199 USDT\n"
        "• PRO – 499 USDT\n"
        "• ELITE – 899 USDT\n\n"
        f"Send the correct amount to this TRC20 address:\n`{USDT_ADDRESS}`\n\n"
        "After sending, tap *Order Now* to submit your payment details."
    )
    kb = [["Order Now"], ["Pricing again"]]
    await update.message.reply_markdown(text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END


async def pricing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["STANDARD", "PRO", "ELITE"]]
    await update.message.reply_text(
        "Select the plan you paid for:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True),
    )
    return PLAN


async def plan_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan = update.message.text.strip().upper()
    if plan not in ("STANDARD", "PRO", "ELITE"):
        await update.message.reply_text("Please choose STANDARD, PRO or ELITE.")
        return PLAN

    context.user_data["plan"] = plan
    await update.message.reply_text(
        "Great. Now paste your *TX hash* (transaction ID) from TronScan:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return TXHASH


async def txhash_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["txhash"] = update.message.text.strip()
    await update.message.reply_text("Got it. Now enter your *email* (license will be tied to this):",
                                    parse_mode="Markdown")
    return EMAIL


async def email_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["email"] = update.message.text.strip()
    await update.message.reply_text(
        "Optional: add any note (Telegram handle, HWID, etc). "
        "If you have nothing to add, type `-`.",
        parse_mode="Markdown",
    )
    return NOTE


async def note_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    if note == "-":
        note = ""
    context.user_data["note"] = note

    user = update.message.from_user
    plan = context.user_data["plan"]
    txhash = context.user_data["txhash"]
    email = context.user_data["email"]

    # Send to admin
    msg = (
        "💳 *New SSB Order*\n\n"
        f"Plan: *{plan}*\n"
        f"Email: `{email}`\n"
        f"TX Hash: `{txhash}`\n"
        f"Note: {note or '(none)'}\n\n"
        f"From user: @{user.username or 'N/A'} (ID: {user.id})"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg, parse_mode="Markdown")

    await update.message.reply_text(
        "Thank you! ✅\n\n"
        "Your payment has been submitted.\n"
        "We usually confirm within a short time. "
        "You will receive your license file (`license.ssb`) by email or Telegram.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Order cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def handle_web_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-responds to the specific format sent by the website."""
    text = update.message.text
    user = update.message.from_user
    
    # 1. Forward to Admin
    admin_msg = (
        f"🚨 <b>WEB ORDER RECEIVED</b>\n"
        f"From: @{user.username} (ID: {user.id})\n\n"
        f"{text}"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="HTML")

    # 2. Extract TxHash (simple heuristic)
    tx_line = [line for line in text.splitlines() if "TX Hash:" in line]
    tx_val = tx_line[0].split("TX Hash:")[1].strip() if tx_line else "provided"

    # 3. Reply to Buyer
    reply_msg = (
        f"<b>✅ Order Received!</b>\n\n"
        f"System is verifying your payment.\n"
        f"<b>TX:</b> <code>{tx_val}</code>\n\n"
        f"⏳ <i>Please allow 10-20 mins for blockchain confirmation.</i>\n"
        f"Once confirmed, your license key + access will be sent here automatically."
    )
    await update.message.reply_text(reply_msg, parse_mode="HTML")
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Order Now$"), order_start),
            CommandHandler("order", order_start),
        ],
        states={
            PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_chosen)],
            TXHASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, txhash_received)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_received)],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Pricing again$"), pricing))
    
    # Auto-handle orders from web
    app.add_handler(MessageHandler(filters.Regex("^🧾 New SSB Order"), handle_web_order))
    
    app.add_handler(conv)

    logger.info("SSB Order Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
