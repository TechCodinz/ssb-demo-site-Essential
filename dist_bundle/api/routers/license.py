"""
SSB PRO API - License Router
Handles: validate, activate, regenerate, bind/unbind device
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import secrets
from datetime import datetime, timedelta

from api.services.jwt_service import verify_token

router = APIRouter()
security = HTTPBearer()

# In-memory license store (replace with database in production)
licenses_db = {}


class LicenseValidateRequest(BaseModel):
    license_key: str
    hwid: str


class LicenseActivateRequest(BaseModel):
    license_key: str
    email: str
    hwid: str


class LicenseBindRequest(BaseModel):
    license_key: str
    hwid: str


def generate_license_key(plan: str) -> str:
    """Generate a unique license key"""
    prefix_map = {
        "cloud_sniper": "SSB-CS",
        "cloud_sniper_pro": "SSB-CSP",
        "cloud_sniper_elite": "SSB-CSE",
        "standard_local": "SSB-STD",
        "pro_local": "SSB-PRO",
        "elite_local": "SSB-ELT"
    }
    prefix = prefix_map.get(plan, "SSB-STD")
    code = secrets.token_hex(4).upper()
    return f"{prefix}-{code[:4]}-{code[4:]}"


@router.post("/validate")
async def validate_license(request: LicenseValidateRequest):
    """Validate a license key and HWID"""
    license_data = licenses_db.get(request.license_key)
    
    if not license_data:
        return {
            "valid": False,
            "error": "License not found"
        }
    
    # Check if expired
    expires = datetime.fromisoformat(license_data["expires"])
    if expires < datetime.utcnow():
        return {
            "valid": False,
            "error": "License expired"
        }
    
    # Check HWID binding
    if license_data["hwid"] and license_data["hwid"] != request.hwid:
        if license_data["hwid"] != "*":
            return {
                "valid": False,
                "error": "HWID mismatch - license bound to different device"
            }
    
    # Generate cloud session
    session_id = secrets.token_hex(16)
    license_data["cloud_session_id"] = session_id
    license_data["last_validated"] = datetime.utcnow().isoformat()
    
    return {
        "valid": True,
        "plan": license_data["plan"],
        "expires": license_data["expires"],
        "cloud_session_id": session_id,
        "features": get_plan_features(license_data["plan"])
    }


@router.post("/activate")
async def activate_license(request: LicenseActivateRequest):
    """Activate a license for the first time"""
    license_data = licenses_db.get(request.license_key)
    
    if not license_data:
        raise HTTPException(status_code=404, detail="License not found")
    
    if license_data["activated"]:
        raise HTTPException(status_code=400, detail="License already activated")
    
    # Bind HWID
    license_data["hwid"] = request.hwid
    license_data["activated"] = True
    license_data["activated_at"] = datetime.utcnow().isoformat()
    license_data["email"] = request.email
    
    return {
        "success": True,
        "activated": True,
        "plan": license_data["plan"],
        "expires": license_data["expires"]
    }


@router.post("/regenerate")
async def regenerate_license(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Regenerate a new license key (admin or user request)"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        
        # Find user's license
        for key, data in licenses_db.items():
            if data.get("email") == email:
                # Generate new key
                new_key = generate_license_key(data["plan"])
                
                # Copy data to new key
                licenses_db[new_key] = {
                    **data,
                    "hwid": "*",  # Reset HWID
                    "activated": False,
                    "regenerated_from": key,
                    "regenerated_at": datetime.utcnow().isoformat()
                }
                
                # Invalidate old key
                del licenses_db[key]
                
                return {
                    "success": True, 
                    "new_key": new_key,
                    "message": "License regenerated. Please activate on new device."
                }
        
        raise HTTPException(status_code=404, detail="No license found for this user")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/bind-device")
async def bind_device(request: LicenseBindRequest):
    """Bind license to a new device HWID"""
    license_data = licenses_db.get(request.license_key)
    
    if not license_data:
        raise HTTPException(status_code=404, detail="License not found")
    
    devices = license_data.get("bound_devices", [])
    max_devices = 2 if "elite" in license_data["plan"] else 1
    
    if len(devices) >= max_devices:
        raise HTTPException(status_code=400, detail=f"Max {max_devices} devices allowed")
    
    if request.hwid not in devices:
        devices.append(request.hwid)
        license_data["bound_devices"] = devices
    
    return {"success": True, "devices_bound": len(devices), "max_devices": max_devices}


@router.post("/unbind-device")
async def unbind_device(request: LicenseBindRequest):
    """Unbind a device from license"""
    license_data = licenses_db.get(request.license_key)
    
    if not license_data:
        raise HTTPException(status_code=404, detail="License not found")
    
    devices = license_data.get("bound_devices", [])
    if request.hwid in devices:
        devices.remove(request.hwid)
        license_data["bound_devices"] = devices
        return {"success": True, "unbound": True}
    
    return {"success": False, "message": "Device not found"}


@router.get("/status")
async def license_status(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get license status for current user"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("email")
        
        for key, data in licenses_db.items():
            if data.get("email") == email:
                return {
                    "license_key": mask_license_key(key),
                    "plan": data["plan"],
                    "expires": data["expires"],
                    "activated": data["activated"],
                    "devices_bound": len(data.get("bound_devices", [])),
                    "last_validated": data.get("last_validated")
                }
        
        return {"has_license": False}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/issue")
async def issue_license(
    plan: str, 
    email: str, 
    months: int = 1,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Issue a new license (admin only)"""
    # TODO: Add admin check
    
    key = generate_license_key(plan)
    expires = datetime.utcnow() + timedelta(days=30 * months)
    
    licenses_db[key] = {
        "key": key,
        "plan": plan,
        "email": email,
        "hwid": "*",
        "activated": False,
        "expires": expires.isoformat(),
        "issued_at": datetime.utcnow().isoformat(),
        "bound_devices": [],
        "cloud_session_id": None
    }
    
    return {
        "success": True,
        "license_key": key,
        "plan": plan,
        "expires": expires.isoformat()
    }


def mask_license_key(key: str) -> str:
    """Mask license key for display: SSB-XXX-XXXX-1234"""
    parts = key.split("-")
    if len(parts) >= 3:
        return f"{parts[0]}-****-****-{parts[-1][-4:]}"
    return "****-****-****"


def get_plan_features(plan: str) -> dict:
    """Get features for a plan"""
    features = {
        "cloud_sniper": {
            "max_trades_per_hour": 5,
            "ai_risk_engine": True,
            "telegram_alerts": False,
            "divine_features": False
        },
        "cloud_sniper_pro": {
            "max_trades_per_hour": 15,
            "ai_risk_engine": True,
            "telegram_alerts": True,
            "divine_features": True
        },
        "cloud_sniper_elite": {
            "max_trades_per_hour": 50,
            "ai_risk_engine": True,
            "telegram_alerts": True,
            "divine_features": True,
            "priority_queue": True,
            "auto_compound": True
        }
    }
    return features.get(plan, features["cloud_sniper"])
