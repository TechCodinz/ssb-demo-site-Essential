"""
Sol Sniper Bot PRO - RPC Admin API
Admin-only endpoints for RPC monitoring and control.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from app.api.routes.cloud_admin import verify_admin_token
from app.services.rpc_manager import rpc_manager, RPCTier, RPCEndpoint

router = APIRouter(prefix="/admin/rpc", tags=["Admin - RPC"])


# ============================================================
# SCHEMAS
# ============================================================

class RPCEndpointResponse(BaseModel):
    id: str
    name: str
    status: str
    enabled: bool
    is_primary: bool
    weight: float
    priority: int
    current_requests: int
    total_requests: int
    total_errors: int
    success_rate: float
    latency_ms: float
    last_health_check: Optional[str]


class RPCStatsResponse(BaseModel):
    tier: str
    total_endpoints: int
    healthy_endpoints: int
    endpoints: List[RPCEndpointResponse]
    top_consumers: List[dict]


class SetWeightRequest(BaseModel):
    endpoint_id: str
    weight: float


class SetTierRequest(BaseModel):
    tier: str  # FREE or PREMIUM


class AddEndpointRequest(BaseModel):
    id: str
    name: str
    url: str
    weight: float = 0.1
    is_primary: bool = False
    priority: int = 5
    max_requests_per_minute: int = 100


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/stats", response_model=RPCStatsResponse)
async def get_rpc_stats_admin(admin_token: str = Depends(verify_admin_token)):
    """Get full RPC statistics (admin only)"""
    stats = rpc_manager.get_stats()
    top_consumers = rpc_manager.get_top_consumers(limit=10)
    
    endpoints = [
        RPCEndpointResponse(
            id=ep["id"],
            name=ep["name"],
            status=ep["status"],
            enabled=ep["enabled"],
            is_primary=ep["is_primary"],
            weight=ep["weight"],
            priority=ep["priority"],
            current_requests=ep["current_requests"],
            total_requests=ep["total_requests"],
            total_errors=ep["total_errors"],
            success_rate=ep["success_rate"],
            latency_ms=ep["latency_ms"],
            last_health_check=ep["last_health_check"]
        )
        for ep in stats["endpoints"]
    ]
    
    return RPCStatsResponse(
        tier=stats["tier"],
        total_endpoints=stats["total_endpoints"],
        healthy_endpoints=stats["healthy_endpoints"],
        endpoints=endpoints,
        top_consumers=top_consumers
    )


@router.post("/set-tier")
async def set_rpc_tier(
    request: SetTierRequest,
    admin_token: str = Depends(verify_admin_token)
):
    """Switch RPC tier between FREE and PREMIUM"""
    if request.tier not in ["FREE", "PREMIUM"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tier must be FREE or PREMIUM"
        )
    
    tier = RPCTier.FREE if request.tier == "FREE" else RPCTier.PREMIUM
    rpc_manager.set_tier(tier)
    
    return {"ok": True, "message": f"RPC tier set to {request.tier}"}


@router.post("/endpoint/{endpoint_id}/enable")
async def enable_endpoint(
    endpoint_id: str,
    admin_token: str = Depends(verify_admin_token)
):
    """Enable an RPC endpoint"""
    if endpoint_id not in rpc_manager.endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    rpc_manager.enable_endpoint(endpoint_id)
    return {"ok": True, "message": f"Endpoint {endpoint_id} enabled"}


@router.post("/endpoint/{endpoint_id}/disable")
async def disable_endpoint(
    endpoint_id: str,
    admin_token: str = Depends(verify_admin_token)
):
    """Disable an RPC endpoint"""
    if endpoint_id not in rpc_manager.endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    rpc_manager.disable_endpoint(endpoint_id)
    return {"ok": True, "message": f"Endpoint {endpoint_id} disabled"}


@router.post("/set-weight")
async def set_endpoint_weight(
    request: SetWeightRequest,
    admin_token: str = Depends(verify_admin_token)
):
    """Set weight for an RPC endpoint"""
    if request.endpoint_id not in rpc_manager.endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    if not 0.01 <= request.weight <= 1.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Weight must be between 0.01 and 1.0"
        )
    
    rpc_manager.set_weight(request.endpoint_id, request.weight)
    return {"ok": True, "message": f"Weight set to {request.weight}"}


@router.post("/add-endpoint")
async def add_endpoint(
    request: AddEndpointRequest,
    admin_token: str = Depends(verify_admin_token)
):
    """Add a new RPC endpoint"""
    if request.id in rpc_manager.endpoints:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Endpoint ID already exists"
        )
    
    endpoint = RPCEndpoint(
        id=request.id,
        name=request.name,
        url=request.url,
        weight=request.weight,
        is_primary=request.is_primary,
        priority=request.priority,
        max_requests_per_minute=request.max_requests_per_minute
    )
    
    rpc_manager.add_endpoint(endpoint)
    return {"ok": True, "message": f"Endpoint {request.id} added"}


@router.delete("/endpoint/{endpoint_id}")
async def remove_endpoint(
    endpoint_id: str,
    admin_token: str = Depends(verify_admin_token)
):
    """Remove an RPC endpoint"""
    if endpoint_id not in rpc_manager.endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    # Don't allow removing the last endpoint
    if len(rpc_manager.endpoints) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last endpoint"
        )
    
    rpc_manager.remove_endpoint(endpoint_id)
    return {"ok": True, "message": f"Endpoint {endpoint_id} removed"}


@router.get("/consumers")
async def get_top_consumers(
    limit: int = 20,
    admin_token: str = Depends(verify_admin_token)
):
    """Get top RPC consumers"""
    return rpc_manager.get_top_consumers(limit=limit)
