# server.py
import os
import json
import time
import uuid
import random
import smtplib
import requests
from email.mime.text import MIMEText
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import uvicorn

# ------------------------------
# CONFIG
# ------------------------------

TRON_WALLET = os.environ.get("TRON_WALLET", "TBxck6t1a3pZE2YLho4Su1PcGKd2yK2zD4")
USDT_CONTRACT = os.environ.get("USDT_CONTRACT", "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj")  # USDT TRC20

# Where we store orders and issued licenses
ORDERS_FILE = "orders.json"
LICENSES_FILE = "licenses_issued.json"

# Email (for sending license to customer)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER or "no-reply@solsniperbot.com")

# Telegram admin notifications
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")

# Optional: GitHub license DB auto-update (can be configured later)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # personal access token
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")    # e.g. "TechCodinz/ssb-license-db"
GITHUB_LICENSE_PATH = os.environ.get("GITHUB_LICENSE_PATH", "licenses.json")

# Plan prices (USDT)
PLANS = {
    "STANDARD": {
        "name": "STANDARD – DRY RUN",
        "price": 199.0,
        "tier": "STANDARD"
    },
    "PRO": {
        "name": "PRO – LIVE TRADING",
        "price": 499.0,
        "tier": "PRO"
    },
    "ELITE": {
        "name": "ELITE – LIFETIME",
        "price": 899.0,
        "tier": "ELITE"
    }
}

# ------------------------------
# HELPERS – JSON STORAGE
# ------------------------------

def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_orders():
    data = _load_json(ORDERS_FILE, {"orders": []})
    if "orders" not in data:
        data["orders"] = []
    return data


def save_orders(data) -> None:
    _save_json(ORDERS_FILE, data)


def load_licenses():
    data = _load_json(LICENSES_FILE, {"licenses": []})
    if "licenses" not in data:
        data["licenses"] = []
    return data


def save_licenses(data) -> None:
    _save_json(LICENSES_FILE, data)


# ------------------------------
# MODELS
# ------------------------------

class CheckoutRequest(BaseModel):
    plan_id: Literal["STANDARD", "PRO", "ELITE"]
    email: EmailStr
    telegram_handle: Optional[str] = None


class CheckoutResponse(BaseModel):
    ok: bool
    order_id: str
    wallet_address: str
    amount_usdt: float
    plan_id: str
    plan_name: str
    message: str


class ConfirmPaymentRequest(BaseModel):
    order_id: str
    tx_hash: str


class ConfirmPaymentResponse(BaseModel):
    ok: bool
    message: str
    license_key: Optional[str] = None
    plan_id: Optional[str] = None


# ------------------------------
# EMAIL / TELEGRAM HELPERS
# ------------------------------

def send_email(to_email: str, subject: str, body: str) -> None:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        print(f"[EMAIL] SMTP not configured. Would send to {to_email}: {subject}")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[EMAIL] Sent to {to_email}")
    except Exception as e:
        print(f"[EMAIL] Error sending email: {e}")


def notify_admin(text: str) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID):
        print(f"[TG-ADMIN] {text}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_ADMIN_CHAT_ID, "text": text},
            timeout=6,
        )
    except Exception as e:
        print(f"[TG-ADMIN] Error sending admin notification: {e}")


# ------------------------------
# LICENSE GENERATION
# ------------------------------

def generate_license_key(plan_id: str) -> str:
    prefix_map = {
        "STANDARD": "SSB-STD",
        "PRO": "SSB-PRO",
        "ELITE": "SSB-ELITE",
    }
    prefix = prefix_map.get(plan_id, "SSB-STD")
    part1 = random.randint(1000, 9999)
    part2 = random.randint(1000, 9999)
    return f"{prefix}-{part1}-{part2}"


def add_license_to_local_db(license_key: str, plan_id: str, email: str, order_id: str):
    db = load_licenses()
    db["licenses"].append(
        {
            "key": license_key,
            "plan": plan_id,
            "email": email,
            "status": "active",
            "expires": "2099-12-31",
            "hwid": "*",
            "order_id": order_id,
            "created_at": int(time.time()),
        }
    )
    save_licenses(db)
    print(f"[LICENSE] Added {license_key} for {email} ({plan_id})")


def try_update_github_license_db(license_key: str, plan_id: str, email: str):
    """
    OPTIONAL: auto-push new license to your GitHub licenses.json (for GUI validation).
    Configure GITHUB_TOKEN, GITHUB_REPO, GITHUB_LICENSE_PATH to enable.
    """
    if not (GITHUB_TOKEN and GITHUB_REPO and GITHUB_LICENSE_PATH):
        print("[GITHUB] Not configured, skipping remote license update.")
        return

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    base_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_LICENSE_PATH}"

    # 1) Get existing file
    resp = requests.get(base_url, headers=headers, timeout=10)
    resp.raise_for_status()
    file_info = resp.json()
    sha = file_info["sha"]
    import base64
    content_raw = base64.b64decode(file_info["content"]).decode("utf-8")
    data = json.loads(content_raw)

    if "licenses" not in data:
        data["licenses"] = []

    data["licenses"].append(
        {
            "key": license_key,
            "plan": plan_id,
            "email": email,
            "status": "active",
            "expires": "2099-12-31",
            "hwid": "*",
        }
    )

    new_content = json.dumps(data, indent=2)
    b64_content = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

    commit_msg = f"Add license {license_key} for {email}"
    update_payload = {
        "message": commit_msg,
        "content": b64_content,
        "sha": sha,
    }
    put_resp = requests.put(base_url, headers=headers, json=update_payload, timeout=10)
    if put_resp.status_code in (200, 201):
        print("[GITHUB] License DB updated on GitHub.")
    else:
        print(f"[GITHUB] Failed to update license DB: {put_resp.status_code} {put_resp.text}")


def issue_license(order: dict, tx_hash: str) -> str:
    """
    Generate license, store it, notify user + admin, and optionally update GitHub.
    Returns license key.
    """
    plan_id = order["plan_id"]
    email = order["email"]
    telegram_handle = order.get("telegram_handle") or ""
    order_id = order["id"]

    license_key = generate_license_key(plan_id)
    add_license_to_local_db(license_key, plan_id, email, order_id)
    try_update_github_license_db(license_key, plan_id, email)

    # Email to customer
    subject = f"Your Sol Sniper Bot PRO license ({plan_id})"
    body = f"""
Hey,

Thank you for purchasing Sol Sniper Bot PRO ({plan_id})!

Your license key:
    {license_key}

Plan: {PLANS[plan_id]["name"]}
TX Hash: {tx_hash}

Download & Activation:
1. Download the bot package from the link the seller provided.
2. Run the GUI (Sol Sniper Bot PRO).
3. When prompted, enter this license key.
4. The bot will validate it and unlock your plan features.

If you have any issues, contact support on Telegram.

– Sol Sniper Bot PRO
"""
    send_email(email, subject, body)

    # Notify admin
    msg = f"✅ NEW ORDER PAID\nPlan: {plan_id}\nEmail: {email}\nTelegram: {telegram_handle}\nAmount: {order['amount_usdt']} USDT\nTX: {tx_hash}\nLicense: {license_key}"
    notify_admin(msg)

    return license_key


# ------------------------------
# TRONSCAN PAYMENT CHECK
# ------------------------------

def verify_tron_usdt_payment(tx_hash: str, expected_amount: float) -> bool:
    """
    Check Tron transaction to confirm USDT payment.
    Uses TronScan API. You can adjust if fields change.

    Returns True if:
      - tx is valid
      - token is USDT_TRON
      - to_address == TRON_WALLET
      - amount >= expected_amount
    """
    try:
        url = "https://apilist.tronscanapi.com/api/transaction-info"
        r = requests.get(url, params={"hash": tx_hash}, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[TRON] Error fetching tx {tx_hash}: {e}")
        return False

    token_info = data.get("tokenTransferInfo") or {}
    to_addr = token_info.get("to_address")
    contract = token_info.get("contract_address")
    amount_raw = token_info.get("amount")
    decimals = token_info.get("decimals") or 6

    if not (to_addr and contract and amount_raw):
        print("[TRON] Missing tokenTransferInfo fields.")
        return False

    # Normalize addresses (Tron addresses are case-sensitive but we do simple check)
    if to_addr != TRON_WALLET:
        print(f"[TRON] To address mismatch: {to_addr} != {TRON_WALLET}")
        return False

    if contract != USDT_CONTRACT:
        print(f"[TRON] Contract mismatch: {contract} != {USDT_CONTRACT}")
        return False

    try:
        amount_usdt = float(amount_raw) / (10 ** int(decimals))
    except Exception:
        # Some APIs return human-readable already – fallback
        try:
            amount_usdt = float(amount_raw)
        except Exception:
            print(f"[TRON] Cannot parse amount: {amount_raw}")
            return False

    print(f"[TRON] TX {tx_hash} amount: {amount_usdt} USDT (expected >= {expected_amount})")

    return amount_usdt >= expected_amount


# ------------------------------
# FASTAPI APP
# ------------------------------

app = FastAPI(title="Sol Sniper Bot PRO Checkout API")

# Allow frontend on same/other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/checkout", response_model=CheckoutResponse)
def create_checkout(payload: CheckoutRequest):
    plan = PLANS.get(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan_id")

    orders_data = load_orders()

    # Unique order amount (we can use exact price or add tiny random decimals later)
    amount = plan["price"]

    order_id = str(uuid.uuid4())
    order = {
        "id": order_id,
        "plan_id": payload.plan_id,
        "email": str(payload.email),
        "telegram_handle": payload.telegram_handle or "",
        "amount_usdt": amount,
        "status": "pending",
        "tx_hash": None,
        "created_at": int(time.time()),
    }
    orders_data["orders"].append(order)
    save_orders(orders_data)

    notify_admin(
        f"🆕 NEW CHECKOUT\nPlan: {payload.plan_id}\nEmail: {payload.email}\nTelegram: {payload.telegram_handle}\nAmount: {amount} USDT\nOrder ID: {order_id}"
    )

    return CheckoutResponse(
        ok=True,
        order_id=order_id,
        wallet_address=TRON_WALLET,
        amount_usdt=amount,
        plan_id=payload.plan_id,
        plan_name=plan["name"],
        message="Order created. Send exact amount in USDT (TRC20) to the wallet, then paste your TX hash to confirm.",
    )


@app.post("/api/confirm-payment", response_model=ConfirmPaymentResponse)
def confirm_payment(payload: ConfirmPaymentRequest):
    orders_data = load_orders()
    orders = orders_data["orders"]

    order = next((o for o in orders if o["id"] == payload.order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order["status"] == "paid":
        return ConfirmPaymentResponse(
            ok=True,
            message="Order already marked as paid. If you didn't get your license, contact support.",
            license_key="(already_sent)",
            plan_id=order["plan_id"],
        )

    plan = PLANS.get(order["plan_id"])
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan in order")

    # Verify on-chain payment
    ok = verify_tron_usdt_payment(payload.tx_hash, plan["price"])
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Payment not found or amount too low. Check your TX hash and try again.",
        )

    # Mark paid
    order["status"] = "paid"
    order["tx_hash"] = payload.tx_hash
    save_orders(orders_data)

    # Issue license
    license_key = issue_license(order, payload.tx_hash)

    return ConfirmPaymentResponse(
        ok=True,
        message="Payment confirmed. License sent to your email.",
        license_key=license_key,
        plan_id=order["plan_id"],
    )


if __name__ == "__main__":
    # Run with: python server.py
    uvicorn.run(app, host="0.0.0.0", port=8000)
