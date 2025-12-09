from flask import Flask, request, jsonify
import requests
import json
import random
import string
from datetime import datetime
import hashlib

app = Flask(__name__)

# ================================
# CONFIG
# ================================
USDT_ADDRESS = "TBxck6t1a3pZE2YLho4Su1PcGKd2yK2zD4"   # Your TRC20 wallet
TRONGRID_API = "https://api.trongrid.io/v1/accounts/"
TELEGRAM_BOT = "SSB_OrderBot"
BOT_TOKEN = "<YOUR_TELEGRAM_BOT_API_TOKEN>"
ADMIN_CHAT_ID = "<YOUR_TELEGRAM_CHAT_ID>"

DATABASE_FILE = "database.json"

PLANS = {
    "STD": 199,
    "PRO": 499,
    "ELITE": 899
}

# ================================
# UTILITIES
# ================================

def load_db():
    try:
        with open(DATABASE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"orders": [], "licenses": []}

def save_db(data):
    with open(DATABASE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def generate_license():
    return "-".join(
        "".join(random.choices(string.ascii_uppercase + string.digits, k=4)) 
        for _ in range(4)
    )

def send_telegram(text):
    url = f"https://api.telegram.org/bot{8580154212:AAEunDZLqIFy9f6NarQdewIqtjm_aI7CIL8}/sendMessage"
    requests.post(url, json={
        "chat_id": ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })

def verify_trc20_payment(tx_hash, expected_amount):
    """Check if a TRC20 USDT transfer was received."""
    url = f"https://api.trongrid.io/v1/transactions/{tx_hash}"
    r = requests.get(url).json()

    try:
        contract = r["contract_data"]
        amount = int(contract["amount"]) / 1_000_000  # USDT decimals
        to_addr = contract["to_address"]
    except:
        return False

    return (
        to_addr.lower() == USDT_ADDRESS.lower() and
        amount >= expected_amount
    )

# ================================
# API: Order Submission
# ================================
@app.route("/submit_order", methods=["POST"])
def submit_order():
    data = request.json
    email = data["email"]
    plan = data["plan"]
    tx_hash = data["tx_hash"]

    if plan not in PLANS:
        return jsonify({"error": "Invalid plan"}), 400

    expected_amount = PLANS[plan]

    # verify transaction
    if not verify_trc20_payment(tx_hash, expected_amount):
        return jsonify({"status": "pending"}), 200  

    # generate license
    license_key = generate_license()
    db = load_db()

    order_entry = {
        "email": email,
        "plan": plan,
        "amount": expected_amount,
        "tx": tx_hash,
        "license": license_key,
        "timestamp": datetime.utcnow().isoformat()
    }

    db["orders"].append(order_entry)
    db["licenses"].append({
        "email": email,
        "license": license_key,
        "plan": plan,
        "active": True,
        "created_at": datetime.utcnow().isoformat()
    })
    save_db(db)

    # telegram alert
    send_telegram(
        f"🔥 <b>New SSB Order</b>\n"
        f"Plan: <b>{plan}</b>\n"
        f"Email: {email}\n"
        f"TX: <code>{tx_hash}</code>\n"
        f"Amount: {expected_amount} USDT\n"
        f"License: <code>{license_key}</code>"
    )

    return jsonify({"status": "confirmed", "license": license_key})

# ================================
# API: Dashboard
# ================================
@app.route("/admin_stats")
def admin_stats():
    token = request.args.get("token")
    if token != "<YOUR_ADMIN_LOGIN_TOKEN>":
        return "Forbidden", 403

    db = load_db()

    licenses = db["licenses"]
    orders = db["orders"]

    total_sales = sum(o["amount"] for o in orders)
    total_users = len(licenses)

    return jsonify({
        "total_sales": total_sales,
        "total_licenses": total_users,
        "orders": orders,
        "licenses": licenses
    })

# ================================
# RUN
# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
