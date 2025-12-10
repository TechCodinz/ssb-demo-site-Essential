import asyncio
import random
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

class SimulationEngine:
    """
    Generates synthetic "Matrix-style" trading data for the Cloud Dashboard.
    Simulates high-frequency scanning and profitability to demonstrate bot capabilities.
    """
    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        
        # Simulation State
        self.session_start = 0.0
        self.total_pnl = 0.0
        self.tokens_scanned = 0
        self.active_trades = 0
        self.logs: List[str] = []
        
        # "Matrix" Config
        self.scan_speed = 0.1  # seconds between scans
        self.trade_probability = 0.05
        self.win_rate = 0.78  # 78% win rate for demo
        
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.session_start = time.time()
        self.total_pnl = 0.0
        self.tokens_scanned = 0
        self.active_trades = 0
        self.logs = ["🚀 Simulation Engine Started via Cloud Node 1..."]
        
        # Start the background loop
        self._task = asyncio.create_task(self._simulation_loop())
        
    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logs.append("🛑 Simulation Engine Stopped.")

    def get_state(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "session_time": int(time.time() - self.session_start) if self.is_running else 0,
            "total_pnl": round(self.total_pnl, 4),
            "tokens_scanned": self.tokens_scanned,
            "active_trades": self.active_trades,
            "recent_logs": self.logs[-15:] # Return last 15 logs
        }

    async def _simulation_loop(self):
        """Core loop generating fake events"""
        tokens = ["SOL", "JUP", "BONK", "WIF", "RAY", "POPCAT", "MYRO", "PRISM", "DUST", "HADES"]
        actions = ["Escaping Rug", "Front-running", "Snipe Entry", "Limit Buy", "Trailing Stop"]
        
        while self.is_running:
            # 1. Increment Scans (Visual noise)
            self.tokens_scanned += random.randint(1, 5)
            
            # 2. Random Event Generation
            chance = random.random()
            
            if chance < 0.15: # 15% chance of a log event
                token = random.choice(tokens)
                action = random.choice(actions)
                self._add_log(f"🔎 Scanning {token}... {action} check passed.")
                
            if chance < self.trade_probability: # Trade execution
                await self._execute_fake_trade()
                
            # 3. PnL Drift (Slowly varying)
            if self.active_trades > 0:
                drift = (random.random() - 0.4) * 0.05 # Slight positive bias
                self.total_pnl += drift

            await asyncio.sleep(self.scan_speed)

    async def _execute_fake_trade(self):
        """Simulates a trade lifecycle"""
        token = random.choice(["PEPE", "DOGE", "SHIB", "FLOKI", "MEME"]) + str(random.randint(1,999))
        self.active_trades += 1
        self._add_log(f"⚡ <span style='color:#4ade80'>SNIPE EXECUTED: {token}</span> @ {random.random():.6f} SOL")
        
        # Simulate hold time
        hold_time = random.uniform(1.0, 4.0)
        await asyncio.sleep(hold_time)
        
        # Result
        is_win = random.random() < self.win_rate
        pnl = random.uniform(0.05, 0.5) if is_win else random.uniform(-0.1, -0.01)
        self.total_pnl += pnl
        self.active_trades -= 1
        
        color = "#4ade80" if is_win else "#f97373"
        result_text = "PROFIT" if is_win else "STOP LOSS"
        self._add_log(f"💰 <span style='color:{color}'>TP HIT: {token} ({result_text})</span> +{pnl:.4f} SOL")

    def _add_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")
        if len(self.logs) > 100:
            self.logs.pop(0)

# Global Instance
sim_engine = SimulationEngine()
