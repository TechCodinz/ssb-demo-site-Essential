"""
Sol Sniper Bot PRO - Telegram Notification Service
Sends trade alerts and divine feature notifications to users via Telegram
"""
import httpx
from typing import Optional
from datetime import datetime
from app.core.config import settings


class TelegramNotifier:
    """Send trade notifications and divine alerts via Telegram Bot API"""
    
    BASE_URL = "https://api.telegram.org/bot"
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
    
    async def send(self, message: str) -> bool:
        """Send a message to the configured chat"""
        if not self.enabled:
            return False
        
        try:
            url = f"{self.BASE_URL}{self.bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                })
                return resp.status_code == 200
        except Exception:
            return False
    
    async def send_new_token(self, mint: str, confidence: float):
        """Send new token alert"""
        msg = (
            "🚀 <b>NEW TOKEN DETECTED</b>\n"
            f"<code>{mint}</code>\n"
            f"Confidence: {confidence:.1f}%"
        )
        await self.send(msg)
    
    async def send_buy(self, mint: str, amount_sol: float, mode: str):
        """Send buy notification"""
        emoji = "🟢" if mode == "LIVE" else "🟡"
        mode_text = "LIVE" if mode == "LIVE" else "DRY-RUN"
        msg = (
            f"{emoji} <b>{mode_text} BUY</b>\n"
            f"Token: <code>{mint[:12]}...</code>\n"
            f"Amount: {amount_sol} SOL"
        )
        await self.send(msg)
    
    async def send_sell(self, mint: str, reason: str, pnl: float):
        """Send sell notification"""
        emoji = "💰" if pnl > 0 else "📉"
        pnl_text = f"+{pnl:.1f}%" if pnl > 0 else f"{pnl:.1f}%"
        msg = (
            f"{emoji} <b>SELL ({reason})</b>\n"
            f"Token: <code>{mint[:12]}...</code>\n"
            f"PnL: {pnl_text}"
        )
        await self.send(msg)
    
    async def send_error(self, error: str):
        """Send error notification"""
        msg = f"❌ <b>ERROR</b>\n{error}"
        await self.send(msg)
    
    async def send_status(self, status: str, details: str = ""):
        """Send status update"""
        msg = f"ℹ️ <b>{status}</b>"
        if details:
            msg += f"\n{details}"
        await self.send(msg)
    
    # ============================================================
    # DIVINE FEATURE ALERTS
    # ============================================================
    
    async def send_signal_alert(self, mint: str, signal_strength: str, confidence: float, reasons: list):
        """Send a trading signal alert"""
        emoji = {"LEGENDARY": "🌟", "ULTRA": "🔥", "STRONG": "💪", "MODERATE": "📊"}.get(signal_strength, "📊")
        reasons_text = "\n".join(f"  • {r}" for r in reasons[:4])
        
        msg = f"""
{emoji} <b>{signal_strength} SIGNAL DETECTED</b> {emoji}

<b>Token:</b> <code>{mint[:20]}...</code>
<b>Confidence:</b> {confidence:.1f}%

<b>Reasons:</b>
{reasons_text}

⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC

<i>🚀 SSB Cloud - Ultra Algorithm v3.0</i>
"""
        await self.send(msg)
    
    async def send_cascade_alert(self, mint: str, signals_aligned: int, expected_move: float):
        """Send momentum cascade alert"""
        msg = f"""
⚡ <b>MOMENTUM CASCADE DETECTED!</b> ⚡

<b>Token:</b> <code>{mint[:20]}...</code>
<b>Signals Aligned:</b> {signals_aligned}/8 🔥
<b>Expected Move:</b> +{expected_move:.0f}%

<b>This is RARE! Multiple signals converging!</b>

⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC

<i>🌟 Divine Detection - SSB Cloud</i>
"""
        await self.send(msg)
    
    async def send_whale_alert(self, whale_name: str, action: str, mint: str, amount_sol: float):
        """Send whale activity alert"""
        msg = f"""
🐋 <b>WHALE ALERT</b>

<b>Whale:</b> {whale_name}
<b>Action:</b> {action}
<b>Token:</b> <code>{mint[:20]}...</code>
<b>Amount:</b> {amount_sol:.2f} SOL

<i>Smart money is moving! 👀</i>
"""
        await self.send(msg)
    
    async def send_achievement_unlocked(self, achievement_name: str, emoji: str, xp_earned: int, new_level: int):
        """Send achievement unlocked notification"""
        msg = f"""
🏆 <b>ACHIEVEMENT UNLOCKED!</b> 🏆

{emoji} <b>{achievement_name}</b>

<b>XP Earned:</b> +{xp_earned} XP
<b>Current Level:</b> {new_level}

<i>Keep grinding! You're amazing! 💪</i>
"""
        await self.send(msg)
    
    async def send_daily_summary(self, trades: int, wins: int, total_pnl: float, best_trade: float, win_rate: float):
        """Send daily trading summary"""
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        
        msg = f"""
📊 <b>DAILY TRADING SUMMARY</b>

<b>Total Trades:</b> {trades}
<b>Wins:</b> {wins} ({win_rate:.1f}%)
<b>Total P&L:</b> {pnl_emoji} {total_pnl:+.4f} SOL
<b>Best Trade:</b> +{best_trade:.1f}%

<i>Another day of sniping complete! 🎯</i>

<b>SSB Cloud - Making crypto profitable</b>
"""
        await self.send(msg)
    
    async def send_tp_hit(self, mint: str, profit_percent: float, profit_sol: float):
        """Send take profit notification"""
        msg = f"""
💰 <b>TAKE PROFIT HIT!</b> 💰

<b>Token:</b> <code>{mint[:20]}...</code>
<b>Profit:</b> +{profit_percent:.1f}%
<b>SOL Gained:</b> +{profit_sol:.4f} SOL

<b>Status:</b> Position closed at target 🎯

<i>Keep stacking with SSB Cloud! 📈</i>
"""
        await self.send(msg)
    
    async def send_protection_alert(self, mint: str, threat_level: str, threats: list):
        """Send protection system alert"""
        msg = f"""
🛡️ <b>PROTECTION ALERT</b>

<b>Token:</b> <code>{mint[:20]}...</code>
<b>Threat Level:</b> {threat_level}

<b>Issues Detected:</b>
{chr(10).join(f'  • {t}' for t in threats[:4])}

<b>Trade BLOCKED by Divine Protection</b>
<i>Your funds are safe 🔒</i>
"""
        await self.send(msg)


# Factory function
def create_notifier(bot_token: Optional[str], chat_id: Optional[str]) -> TelegramNotifier:
    """Create a Telegram notifier instance"""
    return TelegramNotifier(bot_token or "", chat_id or "")

