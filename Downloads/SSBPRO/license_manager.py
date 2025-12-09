import json
import os
import time
import hmac
import hashlib
import platform
import uuid
from typing import Dict, Any

# =========================
#  SECRET (change if you want)
# =========================

SECRET_KEY = "SSB_PRO_LICENSE_V1_1f7b9e24b8e4470a9f7b0c4f91d2a3c5"


def get_hwid() -> str:
    """
    Build a simple hardware fingerprint from OS + hostname + MAC.
    """
    try:
        base = f"{platform.system()}|{platform.node()}|{uuid.getnode()}"
        return hashlib.sha256(base.encode()).hexdigest()[:16]
    except Exception:
        return "UNKNOWN_HWID"


def _sign(payload: Dict[str, Any]) -> str:
    """
    Create signature over core fields so license cannot be edited without
    knowing SECRET_KEY.
    """
    fields = [
        str(payload.get("email", "")),
        str(payload.get("plan", "")),
        str(payload.get("exp", "")),
        str(payload.get("hwid", "")),
        str(payload.get("main_hash", "")),
    ]
    data = "|".join(fields)
    return hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()


def validate_license(
    license_path: str = "license.ssb",
    require_pro: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Validate license file.
    - Checks file existence
    - Checks signature
    - Checks expiry
    - Checks HWID (unless '*' or empty)
    - Checks main.py integrity if main_hash present
    """
    now = int(time.time())

    # Default response
    result = {
        "ok": False,
        "tier": None,
        "email": "",
        "exp": None,
        "reason": "",
        "hwid": get_hwid(),
        "days_left": None,
    }

    if not os.path.exists(license_path):
        if dry_run:
            result.update(
                tier="DEMO",
                reason="No license file – DRY RUN only",
            )
            return result
        result["reason"] = f"License file not found: {license_path}"
        return result

    try:
        with open(license_path, "r", encoding="utf-8") as f:
            lic = json.load(f)
    except Exception as e:
        result["reason"] = f"Invalid license file format: {e}"
        return result

    for key in ("email", "plan", "exp", "hwid", "main_hash", "sig"):
        if key not in lic:
            result["reason"] = f"License missing field: {key}"
            return result

    # Signature check
    sig_expected = _sign(lic)
    if sig_expected != lic.get("sig"):
        result["reason"] = "Invalid license signature (file may be tampered)"
        return result

    email = lic.get("email")
    plan = lic.get("plan")
    exp = int(lic.get("exp"))
    hwid = lic.get("hwid")
    main_hash = lic.get("main_hash")

    # Expiry check
    if exp < now:
        days_ago = int((now - exp) / 86400)
        result.update(
            tier=plan,
            email=email,
            exp=exp,
            reason=f"License expired ({days_ago} days ago)",
            days_left=0,
        )
        return result

    # HWID check (unless wildcard)
    current_hwid = get_hwid()
    if hwid not in ("*", "", None):
        if hwid != current_hwid:
            result.update(
                tier=plan,
                email=email,
                exp=exp,
                reason=f"License locked to different machine (expected {hwid}, got {current_hwid})",
            )
            return result

    # main.py integrity check (lightweight)
    try:
        if os.path.exists("main.py") and main_hash:
            with open("main.py", "rb") as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()
            if current_hash != main_hash:
                result.update(
                    tier=plan,
                    email=email,
                    exp=exp,
                    reason="Bot core code modified (main.py hash mismatch)",
                )
                return result
    except Exception:
        # don't hard fail here, just warn
        pass

    days_left = int((exp - now) / 86400)

    result.update(
        ok=True,
        tier=plan,
        email=email,
        exp=exp,
        reason="License valid",
        hwid=current_hwid,
        days_left=days_left,
    )
    return result


def create_license_payload(
    email: str,
    days: int,
    plan: str = "PRO",
    hwid: str = "*",
    main_file: str = "main.py",
) -> Dict[str, Any]:
    """
    Build a license payload (without writing to disk).
    hwid="*" means any machine; otherwise lock to that HWID.
    """
    now = int(time.time())
    exp = now + days * 86400

    if os.path.exists(main_file):
        with open(main_file, "rb") as f:
            main_hash = hashlib.sha256(f.read()).hexdigest()
    else:
        main_hash = ""

    payload = {
        "email": email,
        "plan": plan,
        "exp": exp,
        "hwid": hwid or "*",
        "main_hash": main_hash,
    }
    payload["sig"] = _sign(payload)
    return payload


def write_license_file(payload: Dict[str, Any], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    # Helper: show your own HWID for manual locking.
    print("Current HWID:", get_hwid())
