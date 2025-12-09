"""
Sol Sniper Bot PRO - Cloud Web Server
=====================================
FastAPI-based web interface for running the bot from any browser.
Users can monitor trades, start/stop the engine, and configure settings.
"""

import asyncio
import json
import os
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from collections import deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ============================================================
# CONFIGURATION
# ============================================================

CONFIG_FILE = "config.json"
LOG_FILE = "logs/bot.log"
LICENSE_FILE = "license.json"

# In-memory state
bot_state = {
    "running": False,
    "mode": "STOPPED",
    "stats": {
        "tokens_seen": 0,
        "tokens_passed": 0,
        "dry_run_buys": 0,
        "live_buys": 0,
        "tp_exits": 0,
        "sl_exits": 0,
        "open_positions": 0
    },
    "positions": {},
    "recent_tokens": deque(maxlen=50),
    "log_buffer": deque(maxlen=200)
}

# WebSocket connections for live updates
active_connections: List[WebSocket] = []

# Bot engine task
bot_task: Optional[asyncio.Task] = None

# ============================================================
# FASTAPI APP SETUP
# ============================================================

app = FastAPI(
    title="Sol Sniper Bot PRO - Cloud",
    description="Cloud-based Solana trading bot interface",
    version="1.0.0"
)

# CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates directory
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# ============================================================
# CONFIG HELPERS
# ============================================================

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "rpc": "",
        "buy_amount_sol": 0.25,
        "min_liquidity_usd": 8000,
        "min_volume_5m": 15000,
        "take_profit_percent": 250,
        "stop_loss_percent": 60,
        "dry_run": True
    }


def save_config(cfg: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def load_license() -> Dict[str, Any]:
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"plan": "DEMO", "email": "", "expires": ""}


# ============================================================
# WEBSOCKET BROADCAST
# ============================================================

async def broadcast(event_type: str, data: Any):
    """Send event to all connected WebSocket clients."""
    message = json.dumps({"type": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()})
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        active_connections.remove(ws)


def add_log(message: str, level: str = "info"):
    """Add log entry and broadcast to clients."""
    entry = {
        "time": datetime.utcnow().strftime("%H:%M:%S"),
        "level": level,
        "message": message
    }
    bot_state["log_buffer"].append(entry)
    # Schedule broadcast in the event loop
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(broadcast("log", entry))
    except RuntimeError:
        pass


# ============================================================
# SIMPLIFIED TRADING ENGINE (for demo - connects to main.py logic)
# ============================================================

async def trading_engine():
    """
    Simplified trading engine that imports from main.py.
    In production, this would integrate with the full engine.
    """
    global bot_state
    
    add_log("⚡ Starting Sol Sniper Bot PRO Cloud Engine...", "success")
    await broadcast("status", {"running": True, "mode": "STARTING"})
    
    try:
        # Import the main trading logic
        import websockets
        
        config = load_config()
        bot_state["mode"] = "DRY RUN" if config.get("dry_run", True) else "LIVE"
        add_log(f"Mode: {bot_state['mode']}", "info")
        
        await broadcast("status", {"running": True, "mode": bot_state["mode"]})
        
        # Connect to Pump.fun WebSocket
        PUMP_WS = "wss://pumpportal.fun/api/data"
        
        while bot_state["running"]:
            try:
                add_log("🔌 Connecting to Pump.fun stream...", "info")
                
                async with websockets.connect(PUMP_WS) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    add_log("✅ Connected to Pump.fun stream!", "success")
                    await broadcast("status", {"running": True, "mode": bot_state["mode"], "connected": True})
                    
                    async for raw in ws:
                        if not bot_state["running"]:
                            break
                            
                        try:
                            msg = json.loads(raw)
                            mint = msg.get("mint")
                            if not mint:
                                continue
                            
                            bot_state["stats"]["tokens_seen"] += 1
                            
                            # Add to recent tokens
                            token_entry = {
                                "mint": mint,
                                "time": datetime.utcnow().strftime("%H:%M:%S"),
                                "status": "NEW"
                            }
                            bot_state["recent_tokens"].appendleft(token_entry)
                            
                            add_log(f"🚀 NEW TOKEN: {mint[:8]}...", "success")
                            await broadcast("token", token_entry)
                            await broadcast("stats", bot_state["stats"])
                            
                        except Exception as e:
                            add_log(f"Error processing message: {e}", "danger")
                            
            except Exception as e:
                add_log(f"⚠️ Connection error: {e}", "warning")
                if bot_state["running"]:
                    add_log("Reconnecting in 3s...", "warning")
                    await asyncio.sleep(3)
                    
    except Exception as e:
        add_log(f"❌ Engine error: {e}", "danger")
    finally:
        bot_state["running"] = False
        bot_state["mode"] = "STOPPED"
        add_log("🛑 Engine stopped", "info")
        await broadcast("status", {"running": False, "mode": "STOPPED"})


# ============================================================
# API ROUTES
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard."""
    config = load_config()
    license_info = load_license()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "config": config,
        "license": license_info,
        "state": bot_state
    })


@app.get("/api/status")
async def get_status():
    """Get current bot status."""
    return {
        "running": bot_state["running"],
        "mode": bot_state["mode"],
        "stats": bot_state["stats"],
        "positions": dict(bot_state["positions"]),
        "recent_tokens": list(bot_state["recent_tokens"])
    }


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    return load_config()


@app.post("/api/config")
async def update_config(request: Request):
    """Update configuration."""
    try:
        new_config = await request.json()
        save_config(new_config)
        add_log("⚙️ Configuration updated", "info")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/start")
async def start_bot():
    """Start the trading engine."""
    global bot_task
    
    if bot_state["running"]:
        return {"success": False, "error": "Bot already running"}
    
    bot_state["running"] = True
    bot_task = asyncio.create_task(trading_engine())
    
    return {"success": True, "message": "Bot started"}


@app.post("/api/stop")
async def stop_bot():
    """Stop the trading engine."""
    global bot_task
    
    bot_state["running"] = False
    
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
        bot_task = None
    
    add_log("🛑 Bot stopped by user", "info")
    return {"success": True, "message": "Bot stopped"}


@app.get("/api/logs")
async def get_logs():
    """Get recent log entries."""
    return list(bot_state["log_buffer"])


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    active_connections.append(websocket)
    
    # Send initial state
    await websocket.send_text(json.dumps({
        "type": "init",
        "data": {
            "running": bot_state["running"],
            "mode": bot_state["mode"],
            "stats": bot_state["stats"],
            "logs": list(bot_state["log_buffer"]),
            "tokens": list(bot_state["recent_tokens"])
        }
    }))
    
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        active_connections.remove(websocket)


# ============================================================
# MAIN ENTRY
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Sol Sniper Bot PRO - Cloud Edition")
    print("  Open http://localhost:8000 in your browser")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
