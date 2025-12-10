from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from app.services.simulation_engine import sim_engine

router = APIRouter(
    prefix="/simulation",
    tags=["simulation"]
)

class SimulationStateResponse(BaseModel):
    is_running: bool
    session_time: int
    total_pnl: float
    tokens_scanned: int
    active_trades: int
    recent_logs: List[str]

@router.post("/start")
async def start_simulation():
    """Start the synthetic simulation engine"""
    await sim_engine.start()
    return {"status": "started", "message": "Simulation engine initialized"}

@router.post("/stop")
async def stop_simulation():
    """Stop the simulation engine"""
    await sim_engine.stop()
    return {"status": "stopped", "message": "Simulation engine halted"}

@router.get("/state", response_model=SimulationStateResponse)
async def get_simulation_state():
    """Get real-time state of the simulation (polled by frontend)"""
    return sim_engine.get_state()
