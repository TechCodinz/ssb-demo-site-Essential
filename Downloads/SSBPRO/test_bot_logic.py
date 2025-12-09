import asyncio
from unittest.mock import MagicMock, AsyncMock
from ssb_order_bot import handle_web_order

# Mock objects to simulate Telegram
class MockUser:
    username = "test_user"
    id = 123456

class MockMessage:
    text = (
        "🧾 New SSB Order\n\n"
        "Plan: PRO (LIVE)\n"
        "Email: test@example.com\n"
        "TX Hash: 88888888\n"
        "Note: Fast delivery pls\n\n"
        "Source: Landing page checkout form"
    )
    from_user = MockUser()
    reply_text = AsyncMock()

class MockUpdate:
    message = MockMessage()

class MockContext:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    user_data = {}

async def run_test():
    print("--- Starting Bot Logic Test ---")
    update = MockUpdate()
    context = MockContext()

    # Run handler
    await handle_web_order(update, context)

    # Verify Admin Forward
    print("\n[1] Verifying Admin Forward...")
    context.bot.send_message.assert_called_once()
    args, kwargs = context.bot.send_message.call_args
    print(f"SUCCESS: Admin message sent to chat_id={kwargs['chat_id']}")
    print(f"CONTENT: {kwargs['text'][:50]}...")

    # Verify User Reply
    print("\n[2] Verifying User Reply...")
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    reply_text = args[0]
    
    if "TX: 88888888" in reply_text and "Order Received" in reply_text:
        print("SUCCESS: Reply contains correct TX hash and confirmation.")
        print(f"REPLY: {reply_text.replace('<b>', '').replace('</b>', '')}")
    else:
        print("FAILURE: Reply missing key info.")

    print("\n--- Test Complete: Logic Validated ---")

if __name__ == "__main__":
    asyncio.run(run_test())
