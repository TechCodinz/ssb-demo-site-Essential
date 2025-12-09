# 🚀 Sol Sniper Bot PRO - Installation Guide

Welcome to **Sol Sniper Bot PRO** - The #1 Pump.fun Solana Trading Bot!

---

## 📦 Package Contents

```
SolSniperBotPRO/
├── gui_main.exe          # Premium GUI interface (RUN THIS)
├── ssb_core.exe          # Core trading engine (Required)
├── config.sample.json    # Configuration template
├── LICENSE.txt           # Your license file
└── README.md             # This file
```

---

## ⚡ Quick Start (5 Minutes)

### Step 1: Setup Configuration (CRITICAL)

1. **Rename** `config.sample.json` to `config.json`.
2. Open `config.json` in Notepad.
3. **Add Your Wallet**:
   - Find `private_key`.
   - Paste your **SOLANA PRIVATE KEY** (Base58 format).
   - *Tip: In Phantom Wallet -> Settings -> Accounts -> Show Private Key.*
4. **Add RPC URL** (Required for speed):
   - Get a free RPC from [Helius.dev](https://helius.dev) or QuickNode.
   - Paste it into `rpc`.

### Step 2: Run the Bot

1. Double-click `gui_main.exe`.
2. Click "Try Free Demo" to test securely.
3. Click "Activate License" when ready to trade LIVE.

### 💰 How to Monitor & Cash Out

1. **Monitor Profits**: Watch the "Session Stats" in the GUI. It tracks buys, sells, and approximate PnL.
2. **Cash Out**: The bot trades directly from your wallet. 
   - Profits stay in YOUR wallet automatically.
   - To cash out, just send SOL/USDC from your wallet to an exchange.

---

## ⚙️ Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `dry_run` | Test mode (no real trades) | `true` |
| `buy_amount_sol` | SOL per trade | `0.25` |
| `take_profit_percent` | Take profit % | `250` |
| `stop_loss_percent` | Stop loss % | `60` |
| `min_liquidity_usd` | Minimum liquidity | `8000` |
| `min_vol_5m` | Minimum 5m volume | `15000` |

---

## 🎯 Plan Features

| Feature | STANDARD | PRO | ELITE |
|---------|----------|-----|-------|
| LIVE Trading | ✅ | ✅ | ✅ |
| Trades/Hour | 7 | 12 | 18 |
| Open Positions | 5 | 8 | 10 |
| Trailing Stop | ❌ | ✅ | ✅ |
| Early Entry | ❌ | ❌ | ✅ |
| Priority Fees | 1x | 1.5x | 2x |

---

## 🔒 Security Tips

1. **Never share your private key** with anyone
2. Use a **dedicated trading wallet** with limited funds
3. Start with **DRY RUN mode** to test
4. Set reasonable **stop-loss** levels

---

## ❓ Support

- Telegram: @SSB_OrderBot
- Email: 

---

## ⚠️ Disclaimer

Trading cryptocurrencies carries significant risk. This software is provided as-is.
Past performance does not guarantee future results. Trade responsibly.

---

**Happy Trading!** 🚀💰
