"""
Sol Sniper Bot PRO - SaaS API Client
Handles communication with the SaaS backend
"""
import httpx
from typing import Optional, Dict, Any

from .constants import SAAS_API_URL, SAAS_API_KEY


class SaaSAPIClient:
    """Client for SaaS backend API"""
    
    def __init__(self, base_url: str = SAAS_API_URL, api_key: str = SAAS_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        }
    
    async def activate_license(
        self,
        email: str,
        plan: str,
        telegram_id: str,
        order_id: str,
        license_type: str = "desktop"
    ) -> Dict[str, Any]:
        """
        Activate a license via the SaaS API
        
        Returns:
            {
                "ok": True,
                "license_key": "SSB-PRO-1234-5678",
                "dashboard_url": "https://..."
            }
        """
        payload = {
            "email": email,
            "plan": plan,
            "telegram_id": telegram_id,
            "order_id": order_id,
            "license_type": license_type,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/telegram/activate",
                    json=payload,
                    headers=self.headers
                )
                
                if resp.status_code == 200:
                    return resp.json()
                else:
                    return {
                        "ok": False,
                        "error": f"API returned {resp.status_code}: {resp.text}"
                    }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e)
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get sales statistics from SaaS API"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/api/telegram/stats",
                    headers=self.headers
                )
                
                if resp.status_code == 200:
                    return resp.json()
                else:
                    return {"error": f"API returned {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def verify_tx(self, tx_hash: str, expected_amount: float) -> Dict[str, Any]:
        """Verify a USDT transaction via backend"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/telegram/verify-tx",
                    json={"tx_hash": tx_hash, "expected_amount": expected_amount},
                    headers=self.headers
                )
                
                if resp.status_code == 200:
                    return resp.json()
                else:
                    return {"ok": False, "error": f"API returned {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# Singleton instance
api_client = SaaSAPIClient()
