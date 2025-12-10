"""
demo_runner.py — Offline demo for buyers (no network, no keys required).

Simulates:
- New Pump.fun token
- Honeypot + Dex filters pass
- DRY-RUN buy
- TP hit

Run:
    python demo_runner.py
"""

import json
import time
import random
from pathlib import Path

cfg = json.loads(Path("config.sample.json").read_text())

def pretty(msg: str):
    print(f"[DEMO] {time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}")

def simulate():
    mint = "DemoMint" + "".join(random.choices("ABCDEF0123456789", k=26))
    pretty(f"Detected new token: {mint}")
    pretty("Running honeypot check -> OK")
    pretty("DexScreener -> Liquidity $12,345 | Vol5m $45,678 -> PASS")
    pretty(f"[DRY RUN] Simulating buy of {cfg.get('buy_amount_sol')} SOL -> simulated-txid-{mint[:6]}")
    pretty("Starting TP/SL monitor...")
    for p in [1.05, 1.3, 2.8, 3.5]:
        time.sleep(1)
        pretty(f"Price update: {p:.2f}x")
    pretty("TAKE PROFIT hit -> SELL executed (simulated)")
    pretty("Demo complete.")

if __name__ == "__main__":
    simulate()
