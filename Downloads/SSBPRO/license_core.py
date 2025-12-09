# license_core.py
import os
import json
import uuid
import platform
import hashlib
import datetime
from typing import Optional, Dict, Any, Tuple

import requests

# Paths
LOCAL_LICENSE_JSON = "license.json"   # for GUI
LOCAL_LICENSE_SSB  = "license.ssb"    # encrypted license for CLI/GUI
CONFIG_FILE        = "config.json"

# ---- YOUR GITHUB RAW URL (edit if needed) ----
LICENSE_DB_URL = "https://raw.githubusercontent.com/TechCodinz/ssb-license-db/main/licenses.json"

# ---- Simple “secret” used for .ssb obfuscation (change this) ----
_SSB_SECRET = "SOL_SNIPER_PRO_SUPER_SECRET_2025_CHANGE_ME"


# ================= HWID HELPERS =================

def get_hwid() -> str:
    raw = f"{platform.node()}|{platform.system()}|{platform.machine()}|{uuid.getnode()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


# ================= SMALL JSON HELPERS =================

def load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_license_expired(exp_str: str) -> bool:
    try:
        if not exp_str:
            return False
        exp = datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
        return datetime.date.today() > exp
    except Exception:
        return True


# ================= ENCRYPTED .SSB LICENSE =================

def _ssb_key() -> bytes:
    return hashlib.sha256(_SSB_SECRET.encode()).digest()


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    klen = len(key)
    return bytes(b ^ key[i % klen] for i, b in enumerate(data))


def encode_ssb(payload: dict) -> bytes:
    """
    Encrypt a license payload dict into opaque bytes.
    """
    raw = json.dumps(payload, separators=(",", ":")).encode()
    key = _ssb_key()
    enc = _xor_bytes(raw, key)
    # add simple integrity hash
    digest = hashlib.sha256(raw).hexdigest().encode()
    return digest + b"." + enc


def decode_ssb(data: bytes) -> Optional[dict]:
    try:
        digest_hex, enc = data.split(b".", 1)
        key = _ssb_key()
        raw = _xor_bytes(enc, key)
        if hashlib.sha256(raw).hexdigest().encode() != digest_hex:
            return None
        return json.loads(raw.decode())
    except Exception:
        return None


def load_local_ssb() -> Optional[dict]:
    if not os.path.exists(LOCAL_LICENSE_SSB):
        return None
    try:
        with open(LOCAL_LICENSE_SSB, "rb") as f:
            blob = f.read()
        return decode_ssb(blob)
    except Exception:
        return None


def save_local_ssb(payload: dict) -> None:
    try:
        blob = encode_ssb(payload)
        with open(LOCAL_LICENSE_SSB, "wb") as f:
            f.write(blob)
    except Exception:
        pass


# ================= ONLINE LICENSE DB =================

def fetch_license_db() -> Optional[dict]:
    try:
        r = requests.get(LICENSE_DB_URL, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def normalize_license_list(db: Any) -> list:
    """
    Accept multiple JSON shapes:
    - { "licenses": [ ... ] }
    - [ ... ]
    - { "key": "...", ... }
    """
    if isinstance(db, dict) and "licenses" in db:
        return db["licenses"]
    if isinstance(db, list):
        return db
    if isinstance(db, dict) and "key" in db:
        return [db]
    return []


def online_find_license(key: str, current_hwid: str) -> Optional[dict]:
    """
    Advanced validator:
    - Accepts any license JSON format
    - Auto-binds HWID on first activation
    - Returns license dict (+ optional 'reject_reason')
    """
    db = fetch_license_db()
    if not db:
        return None

    licenses = normalize_license_list(db)
    key = key.strip()

    for rec in licenses:
        if str(rec.get("key", "")).strip() != key:
            continue

        # Normalize fields
        rec.setdefault("plan", "STANDARD")
        rec.setdefault("expires", "2099-12-31")
        rec.setdefault("status", "active")
        rec.setdefault("hwid", "*")
        rec.setdefault("last_update", datetime.datetime.utcnow().isoformat() + "Z")

        # Status
        if rec["status"] != "active":
            rec["reject_reason"] = "revoked"
            return rec

        # Expiry
        if is_license_expired(rec["expires"]):
            rec["reject_reason"] = "expired"
            return rec

        # HWID logic
        srv_hwid = rec.get("hwid", "*")
        if srv_hwid == "*":
            # Bind to first machine that activates
            rec["hwid"] = current_hwid
            return rec

        if srv_hwid != current_hwid:
            rec["reject_reason"] = "hwid_mismatch"
            rec["bound_hwid"] = srv_hwid
            return rec

        # Valid
        return rec

    return None


# ================= GRACE MODE + INTEGRITY =================

def grace_mode_allowed(local_license: Optional[dict], hours: int = 48) -> bool:
    if not local_license:
        return False
    last_ok = local_license.get("last_online_ok")
    if not last_ok:
        return False
    try:
        last = datetime.datetime.fromisoformat(last_ok.replace("Z", ""))
        now = datetime.datetime.utcnow()
        return (now - last).total_seconds() / 3600 <= hours
    except Exception:
        return False


def update_last_online_ok(local_license: dict) -> None:
    local_license["last_online_ok"] = datetime.datetime.utcnow().isoformat() + "Z"
    save_json(LOCAL_LICENSE_JSON, local_license)


def load_local_json_license() -> Optional[dict]:
    return load_json(LOCAL_LICENSE_JSON)


def save_local_json_license(data: dict) -> None:
    save_json(LOCAL_LICENSE_JSON, data)


def check_license_integrity() -> bool:
    """
    Very simple anti-tamper: store hash of license.json in config.json
    and complain if it's modified by hand.
    """
    lic = load_local_json_license()
    if not lic:
        return True  # nothing to check yet

    raw = json.dumps(lic, sort_keys=True, separators=(",", ":")).encode()
    h = hashlib.sha256(raw).hexdigest()

    cfg = load_json(CONFIG_FILE) or {}
    stored = cfg.get("license_hash")

    if stored and stored != h:
        return False

    cfg["license_hash"] = h
    save_json(CONFIG_FILE, cfg)
    return True


# ================= HIGH LEVEL CHECKS =================

def validate_license_for_runtime() -> Tuple[str, Optional[dict]]:
    """
    Used by main.py (CLI bot).
    Returns (tier, info_dict or None)

    tier can be:
        "NONE"  -> no license, demo DRY RUN
        "STD"   -> STANDARD
        "PRO"   -> PRO
        "ELITE" -> ELITE
    """

    hwid = get_hwid()

    # 1) Try encrypted .ssb first (offline)
    ssb = load_local_ssb()
    if ssb and not is_license_expired(ssb.get("expires", "")):
        if ssb.get("hwid") in ("*", hwid):
            plan = ssb.get("plan", "STANDARD").upper()
            return plan_short(plan), ssb

    # 2) Fallback to json license
    if not check_license_integrity():
        return "NONE", {"reason": "license_tampered"}

    lic = load_local_json_license()
    if lic:
        if is_license_expired(lic.get("expires", "")):
            return "NONE", {"reason": "expired"}

        saved_hwid = lic.get("hwid", "*")
        if saved_hwid not in ("*", hwid):
            return "NONE", {"reason": "hwid_mismatch", "bound_hwid": saved_hwid}

        if lic.get("status", "active") != "active":
            return "NONE", {"reason": "revoked"}

        if grace_mode_allowed(lic, hours=48):
            return plan_short(lic.get("plan", "STANDARD")), lic

        # If grace expired we still return plan, but caller may choose to
        # force online re-check. For CLI we keep it simple:
        return plan_short(lic.get("plan", "STANDARD")), lic

    # 3) No license → DEMO
    return "NONE", None


def plan_short(plan: str) -> str:
    plan = (plan or "").upper()
    if plan.startswith("ELITE"):
        return "ELITE"
    if plan.startswith("PRO"):
        return "PRO"
    if plan.startswith("STD") or plan.startswith("STANDARD"):
        return "STD"
    return "NONE"
