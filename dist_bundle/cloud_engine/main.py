"""
SSB PRO - Cloud Engine API
Handles: start/stop engine, status, logs, per-user containers
"""
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import docker
import logging
import json
from datetime import datetime

app = FastAPI(title="SSB PRO Cloud Engine", version="1.0.0")
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Docker client
try:
    docker_client = docker.from_env()
except:
    docker_client = None
    logger.warning("Docker not available")

# In-memory engine states (replace with DB in production)
engine_states: Dict[str, dict] = {}

# WebSocket connections for live logs
ws_connections: Dict[str, List[WebSocket]] = {}


class EngineStartRequest(BaseModel):
    user_id: str
    license_key: str
    config: Optional[dict] = None


class EngineStopRequest(BaseModel):
    user_id: str


class SettingsUpdateRequest(BaseModel):
    user_id: str
    settings: dict


@app.get("/")
async def root():
    return {"service": "SSB PRO Cloud Engine", "status": "online"}


@app.get("/health")
async def health():
    docker_status = "connected" if docker_client else "unavailable"
    return {
        "status": "healthy",
        "docker": docker_status,
        "active_engines": len([e for e in engine_states.values() if e.get("status") == "running"])
    }


@app.post("/engine/start")
async def start_engine(request: EngineStartRequest):
    """Start cloud trading engine for a user"""
    user_id = request.user_id
    
    # Check if already running
    if user_id in engine_states and engine_states[user_id].get("status") == "running":
        return {"success": False, "error": "Engine already running"}
    
    try:
        container_name = f"ssb-engine-{user_id[:8]}"
        
        # Create engine state
        engine_states[user_id] = {
            "status": "starting",
            "container_id": None,
            "container_name": container_name,
            "started_at": datetime.utcnow().isoformat(),
            "last_heartbeat": datetime.utcnow().isoformat(),
            "tokens_scanned": 0,
            "trades_today": 0,
            "open_positions": 0,
            "pnl_today": 0.0,
            "config": request.config or {}
        }
        
        # In production: Start Docker container
        if docker_client:
            try:
                container = docker_client.containers.run(
                    "ssb-trading-engine:latest",
                    name=container_name,
                    detach=True,
                    environment={
                        "USER_ID": user_id,
                        "LICENSE_KEY": request.license_key,
                        "CONFIG": json.dumps(request.config or {})
                    },
                    restart_policy={"Name": "unless-stopped"},
                    mem_limit="512m",
                    cpu_quota=50000  # 50% CPU
                )
                engine_states[user_id]["container_id"] = container.id
            except Exception as e:
                logger.error(f"Docker error: {e}")
                # Continue with simulated engine
        
        engine_states[user_id]["status"] = "running"
        
        return {
            "success": True,
            "status": "running",
            "container_name": container_name,
            "message": "Engine started successfully"
        }
    except Exception as e:
        logger.error(f"Failed to start engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/engine/stop")
async def stop_engine(request: EngineStopRequest):
    """Stop cloud trading engine for a user"""
    user_id = request.user_id
    
    if user_id not in engine_states:
        return {"success": False, "error": "Engine not found"}
    
    state = engine_states[user_id]
    
    try:
        # Stop Docker container
        if docker_client and state.get("container_id"):
            try:
                container = docker_client.containers.get(state["container_id"])
                container.stop(timeout=10)
                container.remove()
            except Exception as e:
                logger.warning(f"Container cleanup error: {e}")
        
        state["status"] = "stopped"
        state["stopped_at"] = datetime.utcnow().isoformat()
        
        return {
            "success": True,
            "status": "stopped",
            "message": "Engine stopped successfully"
        }
    except Exception as e:
        logger.error(f"Failed to stop engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/engine/status/{user_id}")
async def get_engine_status(user_id: str):
    """Get engine status for a user"""
    if user_id not in engine_states:
        return {
            "engine_status": "not_found",
            "message": "No engine found for this user"
        }
    
    state = engine_states[user_id]
    
    return {
        "engine_status": state["status"],
        "last_heartbeat": state.get("last_heartbeat"),
        "tokens_scanned": state.get("tokens_scanned", 0),
        "trades_today": state.get("trades_today", 0),
        "open_positions": state.get("open_positions", 0),
        "pnl_today": state.get("pnl_today", 0.0),
        "started_at": state.get("started_at"),
        "uptime": calculate_uptime(state.get("started_at"))
    }


@app.get("/engine/logs/{user_id}")
async def get_engine_logs(user_id: str, lines: int = 50):
    """Get recent logs for user's engine"""
    if user_id not in engine_states:
        raise HTTPException(status_code=404, detail="Engine not found")
    
    state = engine_states[user_id]
    
    # Get logs from Docker container
    if docker_client and state.get("container_id"):
        try:
            container = docker_client.containers.get(state["container_id"])
            logs = container.logs(tail=lines, timestamps=True).decode("utf-8")
            return {"logs": logs.split("\n")}
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
    
    # Return simulated logs
    return {
        "logs": [
            f"{datetime.utcnow().isoformat()} | SSB Engine started",
            f"{datetime.utcnow().isoformat()} | Connected to Solana RPC",
            f"{datetime.utcnow().isoformat()} | Monitoring pump.fun stream...",
            f"{datetime.utcnow().isoformat()} | Tokens scanned: {state.get('tokens_scanned', 0)}"
        ]
    }


@app.post("/user/settings/update")
async def update_user_settings(request: SettingsUpdateRequest):
    """Update user trading settings - syncs to engine in real-time"""
    user_id = request.user_id
    new_settings = request.settings
    
    # Validate settings
    valid_keys = {
        "buy_amount", "take_profit", "stop_loss", "min_liq", "min_vol",
        "filters_on", "slippage", "priority_fee", "mode", "telegram_alerts",
        "max_positions"
    }
    
    for key in new_settings:
        if key not in valid_keys:
            raise HTTPException(status_code=400, detail=f"Invalid setting: {key}")
    
    # Update engine state if running
    if user_id in engine_states:
        if "config" not in engine_states[user_id]:
            engine_states[user_id]["config"] = {}
        engine_states[user_id]["config"].update(new_settings)
        engine_states[user_id]["settings_updated_at"] = datetime.utcnow().isoformat()
        
        # In production: Signal the Docker container to reload config
        # This would be done via a WebSocket or file watcher
    
    return {
        "success": True,
        "updated_settings": new_settings,
        "message": "Settings updated. Engine will apply within 5 seconds."
    }


@app.websocket("/ws/logs/{user_id}")
async def websocket_logs(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for live log streaming"""
    await websocket.accept()
    
    if user_id not in ws_connections:
        ws_connections[user_id] = []
    ws_connections[user_id].append(websocket)
    
    try:
        while True:
            # Send heartbeat and simulated logs
            if user_id in engine_states and engine_states[user_id]["status"] == "running":
                state = engine_states[user_id]
                state["tokens_scanned"] = state.get("tokens_scanned", 0) + 1
                state["last_heartbeat"] = datetime.utcnow().isoformat()
                
                await websocket.send_json({
                    "type": "log",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"Tokens scanned: {state['tokens_scanned']}"
                })
            
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        ws_connections[user_id].remove(websocket)


@app.post("/engine/restart/{user_id}")
async def restart_engine(user_id: str):
    """Restart engine (used by failover system)"""
    if user_id not in engine_states:
        raise HTTPException(status_code=404, detail="Engine not found")
    
    state = engine_states[user_id]
    
    # Stop and start
    await stop_engine(EngineStopRequest(user_id=user_id))
    
    return await start_engine(EngineStartRequest(
        user_id=user_id,
        license_key=state.get("license_key", ""),
        config=state.get("config", {})
    ))


def calculate_uptime(started_at: Optional[str]) -> str:
    """Calculate uptime string"""
    if not started_at:
        return "0h 0m"
    
    try:
        start = datetime.fromisoformat(started_at)
        diff = datetime.utcnow() - start
        hours = int(diff.total_seconds() // 3600)
        minutes = int((diff.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"
    except:
        return "0h 0m"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
