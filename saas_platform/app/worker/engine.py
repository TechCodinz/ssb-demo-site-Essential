"""
Sol Sniper Bot PRO - Worker Engine
Background process that runs trading bots for users
Integrates with the main.py trading engine
"""
import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Import core modules
from app.core.config import settings
from app.core.database import async_session_maker
from app.models.models import (
    BotInstance, BotLog, BotStatus, BotMode, LogLevel
)
from app.services.redis_service import redis_service
from app.worker.ultra_algorithm import (
    UltraSnipeAlgorithm, TrailingStopEngine, ProfitOptimizer,
    TokenMetrics, TradeOpportunity, TradeResult, SignalStrength
)
from app.worker.divine_features import (
    ai_sentiment, cascade_detector, smart_money, gamification,
    divine_protection, auto_compound, market_regime,
    SentimentLevel, ThreatLevel
)


# Engine Profiles (from main.py)
ENGINE_PROFILES = {
    "STANDARD": {
        "dex_initial_delay": 2.0,
        "risk_multiplier": 0.95,
        "min_conf_add": 5.0,
        "max_trades_mult": 0.6,
        "max_positions_mult": 0.6,
        "trailing_stop_enabled": False,
        "early_entry_boost": 0.0,
        "priority_fee_mult": 1.0,
    },
    "PRO": {
        "dex_initial_delay": 1.5,
        "risk_multiplier": 1.0,
        "min_conf_add": 0.0,
        "max_trades_mult": 1.0,
        "max_positions_mult": 1.0,
        "trailing_stop_enabled": True,
        "early_entry_boost": 0.0,
        "priority_fee_mult": 1.5,
    },
    "ELITE": {
        "dex_initial_delay": 1.0,
        "risk_multiplier": 1.05,
        "min_conf_add": -3.0,
        "max_trades_mult": 1.5,
        "max_positions_mult": 1.3,
        "trailing_stop_enabled": True,
        "early_entry_boost": 0.5,
        "priority_fee_mult": 2.0,
    },
}

# Active bot tasks
active_bots: Dict[str, asyncio.Task] = {}


class BotWorkerEngine:
    """
    Worker engine that handles bot execution.
    Enhanced with Ultra Snipe Algorithm for maximum profitability.
    """
    
    def __init__(self, user_id: str, bot_id: str, config: dict):
        self.user_id = user_id
        self.bot_id = bot_id
        self.config = config
        self.running = False
        
        # Initialize the Ultra Algorithm
        engine_profile = config.get("engine_profile", "PRO")
        self.ultra = UltraSnipeAlgorithm(plan=engine_profile)
        self.profit_optimizer = ProfitOptimizer()
        self.active_positions: Dict[str, dict] = {}
        self.trailing_stops: Dict[str, TrailingStopEngine] = {}
        
        self.stats = {
            "tokens_seen": 0,
            "tokens_passed": 0,
            "tokens_analyzed": 0,
            "legendary_signals": 0,
            "ultra_signals": 0,
            "strong_signals": 0,
            "dry_run_buys": 0,
            "live_buys": 0,
            "tp_exits": 0,
            "sl_exits": 0,
            "trailing_exits": 0,
            "total_pnl_percent": 0.0,
            "win_count": 0,
            "loss_count": 0,
        }
    
    async def log(self, message: str, level: str = "info"):
        """Log a message to database and Redis"""
        async with async_session_maker() as db:
            log_entry = BotLog(
                bot_instance_id=UUID(self.bot_id),
                level=LogLevel(level),
                message=message
            )
            db.add(log_entry)
            await db.commit()
        
        # Publish to Redis for live streaming
        await redis_service.publish_log(self.bot_id, {
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        })
    
    async def update_status(self, status: BotStatus):
        """Update bot status in database"""
        async with async_session_maker() as db:
            await db.execute(
                update(BotInstance)
                .where(BotInstance.id == UUID(self.bot_id))
                .values(status=status, updated_at=datetime.utcnow())
            )
            await db.commit()
    
    async def run(self):
        """Main bot execution loop with Ultra Algorithm"""
        self.running = True
        engine_profile = self.config.get("engine_profile", "PRO")
        mode = self.config.get("mode", "DRY_RUN")
        
        # Get engine settings
        engine = ENGINE_PROFILES.get(engine_profile, ENGINE_PROFILES["PRO"])
        
        try:
            await self.update_status(BotStatus.RUNNING)
            await self.log(f"⚡ Bot started in {mode} mode", "success")
            await self.log(f"🎯 Engine: {engine_profile} | Ultra Algorithm v3.0 ACTIVE", "info")
            await self.log(f"🧠 AI Pattern Recognition: ENABLED", "info")
            await self.log(f"📊 Confidence Threshold: {self.ultra.thresholds['min_confidence']}%", "info")
            
            # Import websockets for Pump.fun connection
            import websockets
            
            PUMP_WS = "wss://pumpportal.fun/api/data"
            
            while self.running:
                try:
                    await self.log("🔌 Connecting to Pump.fun stream...", "info")
                    
                    async with websockets.connect(PUMP_WS) as ws:
                        await ws.send(json.dumps({"method": "subscribeNewToken"}))
                        await self.log("✅ Connected! Scanning for opportunities...", "success")
                        
                        async for raw in ws:
                            if not self.running:
                                break
                            
                            try:
                                msg = json.loads(raw)
                                mint = msg.get("mint")
                                if not mint:
                                    continue
                                
                                self.stats["tokens_seen"] += 1
                                
                                # === PHASE 1: SCAN ===
                                metrics = await self.ultra.scan_token(mint, msg)
                                if not metrics:
                                    continue  # Failed quick filters
                                
                                self.stats["tokens_analyzed"] += 1
                                
                                # Apply engine delay (early entry boost for ELITE)
                                effective_delay = max(0.3, engine["dex_initial_delay"] - engine["early_entry_boost"])
                                await asyncio.sleep(effective_delay)
                                
                                # === PHASE 2-5: ANALYZE, SCORE, OPTIMIZE, EXECUTE ===
                                opportunity = await self.ultra.create_opportunity(
                                    metrics=metrics,
                                    market_data=msg,
                                    current_price=msg.get("price", 0.001),
                                    base_amount=self.config.get("buy_amount_sol", 0.25),
                                    current_positions=len(self.active_positions),
                                    max_positions=self.config.get("max_open_positions", 5)
                                )
                                
                                if not opportunity:
                                    await self.log(
                                        f"❌ {mint[:8]} - Below confidence threshold",
                                        "danger"
                                    )
                                    continue
                                
                                # Log signal strength
                                self.stats["tokens_passed"] += 1
                                signal_emoji = self._get_signal_emoji(opportunity.signal_strength)
                                
                                if opportunity.signal_strength == SignalStrength.LEGENDARY:
                                    self.stats["legendary_signals"] += 1
                                    await self.log(
                                        f"🌟 LEGENDARY SIGNAL: {mint[:8]} ({opportunity.confidence:.1f}%)",
                                        "success"
                                    )
                                elif opportunity.signal_strength == SignalStrength.ULTRA:
                                    self.stats["ultra_signals"] += 1
                                    await self.log(
                                        f"🔥 ULTRA SIGNAL: {mint[:8]} ({opportunity.confidence:.1f}%)",
                                        "success"
                                    )
                                else:
                                    self.stats["strong_signals"] += 1
                                    await self.log(
                                        f"{signal_emoji} {opportunity.signal_strength.name}: {mint[:8]} ({opportunity.confidence:.1f}%)",
                                        "info"
                                    )
                                
                                # Log reasons
                                for reason in opportunity.reasons[:3]:
                                    await self.log(f"   {reason}", "info")
                                
                                # Execute trade
                                if mode == "DRY_RUN":
                                    self.stats["dry_run_buys"] += 1
                                    await self.log(
                                        f"🟡 DRY-RUN BUY: {opportunity.position_size:.3f} SOL → {mint[:8]}",
                                        "warning"
                                    )
                                    await self.log(
                                        f"   TP: +{(opportunity.target_tp/opportunity.entry_price - 1)*100:.1f}% | SL: -{(1 - opportunity.target_sl/opportunity.entry_price)*100:.1f}%",
                                        "info"
                                    )
                                    
                                    # Track position for simulation
                                    self.active_positions[mint] = {
                                        "entry_price": opportunity.entry_price,
                                        "position_size": opportunity.position_size,
                                        "target_tp": opportunity.target_tp,
                                        "target_sl": opportunity.target_sl,
                                        "entry_time": datetime.utcnow()
                                    }
                                    
                                    # Initialize trailing stop if enabled
                                    if engine["trailing_stop_enabled"]:
                                        sl_percent = (1 - opportunity.target_sl/opportunity.entry_price) * 100
                                        self.trailing_stops[mint] = TrailingStopEngine(
                                            initial_sl=sl_percent,
                                            strategy="dynamic"
                                        )
                                else:
                                    # LIVE MODE
                                    self.stats["live_buys"] += 1
                                    
                                    # Execute Swap
                                    try:
                                        tx_sig = await self.execute_solana_swap(
                                            mint=mint,
                                            amount_sol=opportunity.position_size,
                                            slippage_bps=int(self.config.get("slippage", 1.0) * 100)
                                        )
                                        
                                        if tx_sig:
                                            await self.log(
                                                f"🟢 LIVE BUY EXECUTED: {opportunity.position_size:.3f} SOL → {mint[:8]}",
                                                "success"
                                            )
                                            await self.log(
                                                f"   🔗 TX: https://solscan.io/tx/{tx_sig}",
                                                "info"
                                            )
                                            
                                            # Track position
                                            self.active_positions[mint] = {
                                                "entry_price": opportunity.entry_price,
                                                "position_size": opportunity.position_size,
                                                "target_tp": opportunity.target_tp,
                                                "target_sl": opportunity.target_sl,
                                                "tx_sig": tx_sig,
                                                "entry_time": datetime.utcnow()
                                            }
                                        else:
                                            await self.log("❌ Swap failed (no signature returned)", "danger")
                                            
                                    except Exception as swap_err:
                                        await self.log(f"❌ Swap Exec Error: {str(swap_err)}", "danger")

                            except Exception as e:
                                await self.log(f"Error processing token: {e}", "danger")
                                
                except Exception as e:
                    await self.log(f"⚠️ Connection error: {e}", "warning")
                    if self.running:
                        await self.log("Reconnecting in 5s...", "warning")
                        await asyncio.sleep(5)
                        
        except asyncio.CancelledError:
            await self.log("🛑 Bot task cancelled", "info")
        except Exception as e:
            await self.log(f"❌ Bot error: {e}", "danger")
            await self.update_status(BotStatus.ERROR)
        finally:
            self.running = False
            await self.update_status(BotStatus.STOPPED)
            # Log final stats...

    # ==================== TRADING LOGIC ====================
    
    def _decrypt_key(self, token: str) -> str:
        """Decrypt private key using system secret"""
        import hashlib
        import base64
        from cryptography.fernet import Fernet
        
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        cipher = Fernet(base64.urlsafe_b64encode(key))
        return cipher.decrypt(token.encode()).decode()

    async def execute_solana_swap(self, mint: str, amount_sol: float, slippage_bps: int = 100) -> Optional[str]:
        """
        Execute a swap on Solana using Jupiter Aggregator V6 API.
        1. Get Quote
        2. Get Swap Transaction
        3. Sign and Send
        """
        import httpx
        import base64
        import base58
        from solders.keypair import Keypair
        from solders.transaction import VersionedTransaction
        from solana.rpc.async_api import AsyncClient
        from solana.rpc.commitment import Confirmed
        from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
        
        try:
            # 1. Decrypt Wallet
            encrypted_key = self.config.get("private_key")
            if not encrypted_key:
                await self.log("❌ No private key configured", "danger")
                return None
            
            private_key_base58 = self._decrypt_key(encrypted_key)
            keypair = Keypair.from_base58_string(private_key_base58)
            wallet_pubkey = str(keypair.pubkey())
            
            # 2. Setup RPC
            rpc_url = self.config.get("rpc_url") or settings.RPC_URL or "https://api.mainnet-beta.solana.com"
            async_client = AsyncClient(rpc_url)
            
            # 3. Get Quote from Jupiter
            # Input is SOL (So11111111111111111111111111111111111111112)
            SOL_MINT = "So11111111111111111111111111111111111111112"
            amount_lamports = int(amount_sol * 1_000_000_000)
            
            quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={SOL_MINT}&outputMint={mint}&amount={amount_lamports}&slippageBps={slippage_bps}"
            
            async with httpx.AsyncClient() as client:
                quote_res = await client.get(quote_url)
                if quote_res.status_code != 200:
                    await self.log(f"❌ Jupiter Quote Failed: {quote_res.text}", "danger")
                    return None
                
                quote_data = quote_res.json()
                
                # 4. Get Swap Transaction
                swap_payload = {
                    "quoteResponse": quote_data,
                    "userPublicKey": wallet_pubkey,
                    "wrapAndUnwrapSol": True,
                    # Optimize for speed with dynamic priority fees handled by Jupiter or manually
                    "dynamicComputeUnitLimit": True, 
                    "prioritizationFeeLamports": "auto" 
                }
                
                swap_res = await client.post("https://quote-api.jup.ag/v6/swap", json=swap_payload)
                if swap_res.status_code != 200:
                    await self.log(f"❌ Jupiter Swap Gen Failed: {swap_res.text}", "danger")
                    return None
                
                swap_data = swap_res.json()
                swap_transaction_buf = swap_data["swapTransaction"]
                
                # 5. Sign and Send
                raw_tx = base64.b64decode(swap_transaction_buf)
                tx = VersionedTransaction.from_bytes(raw_tx)
                
                # Sign
                signature = keypair.sign_message(tx.message.to_bytes_versioned(tx.message))
                signed_tx = VersionedTransaction.populate(tx.message, [signature])
                
                # Send
                opts = settings.TX_OPTS if hasattr(settings, 'TX_OPTS') else None
                # Use basic send if no special opts
                
                # We use solders to send, or AsyncClient
                # AsyncClient.send_transaction expects a VersionedTransaction object or bytes
                
                # Note: solana-py 0.30+ changes how send_transaction works.
                # We send the serialized byte content.
                
                # Using httpx to send to RPC directly for maximum control if AsyncClient has issues, 
                # but let's try AsyncClient first as it handles encoding.
                
                resp = await async_client.send_transaction(
                    signed_tx, 
                    opts=None
                )
                
                await async_client.close()
                return str(resp.value)
                
        except Exception as e:
            await self.log(f"❌ FATAL SWAP ERROR: {str(e)}", "danger")
            return None
            await self.log(f"   Opportunities Found: {self.stats['tokens_passed']}", "info")
            await self.log(f"   Trades: {self.stats['dry_run_buys'] + self.stats['live_buys']}", "info")
            await self.log(f"   Win Rate: {win_rate:.1f}%", "info")
            await self.log("🛑 Bot stopped", "info")
    
    def _get_signal_emoji(self, strength: SignalStrength) -> str:
        """Get emoji for signal strength"""
        return {
            SignalStrength.LEGENDARY: "🌟",
            SignalStrength.ULTRA: "🔥",
            SignalStrength.STRONG: "💪",
            SignalStrength.MODERATE: "📊",
            SignalStrength.WEAK: "📉"
        }.get(strength, "📊")
    
    def stop(self):
        """Stop the bot"""
        self.running = False



async def handle_command(command: dict):
    """Handle a command from Redis"""
    action = command.get("action")
    user_id = command.get("user_id")
    bot_id = command.get("bot_id")
    
    if action == "start":
        # Stop existing if any
        if user_id in active_bots:
            active_bots[user_id].cancel()
            try:
                await active_bots[user_id]
            except asyncio.CancelledError:
                pass
        
        # Create and start new bot
        config = command.get("config", {})
        config["mode"] = command.get("mode", "DRY_RUN")
        config["engine_profile"] = command.get("engine_profile", "PRO")
        
        engine = BotWorkerEngine(user_id, bot_id, config)
        task = asyncio.create_task(engine.run())
        active_bots[user_id] = task
        
        print(f"[WORKER] Started bot for user {user_id}")
        
    elif action == "stop":
        if user_id in active_bots:
            active_bots[user_id].cancel()
            try:
                await active_bots[user_id]
            except asyncio.CancelledError:
                pass
            del active_bots[user_id]
            print(f"[WORKER] Stopped bot for user {user_id}")


async def worker_main():
    """Main worker process"""
    print("\n" + "="*60)
    print("  Sol Sniper Bot PRO - Worker Engine")
    print("  Listening for bot commands...")
    print("="*60 + "\n")
    
    await redis_service.connect()
    
    # Subscribe to all command channels using pattern
    client = await redis_service.connect()
    pubsub = client.pubsub()
    await pubsub.psubscribe("commands:*")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    data = json.loads(message["data"])
                    await handle_command(data)
                except Exception as e:
                    print(f"[WORKER] Error handling command: {e}")
    except asyncio.CancelledError:
        print("[WORKER] Shutting down...")
    finally:
        await redis_service.disconnect()


if __name__ == "__main__":
    asyncio.run(worker_main())
