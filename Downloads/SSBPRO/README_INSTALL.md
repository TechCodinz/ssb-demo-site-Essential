# LeanTraderBot Mini v4 — Installation Guide

This guide works for:
- Windows 10/11
- Linux (Ubuntu, Debian, CentOS)
- macOS
- Android Termux (optional)

---

# 1. WINDOWS INSTALLATION

## Step 1 — Install Python 3.10–3.13
Download from:
https://www.python.org/downloads/

Check “Add to PATH”.

## Step 2 — Run the installer
Double-click:



install_windows.bat


It will:
- Create venv  
- Activate it  
- Install dependencies  

## Step 3 — Test demo mode
Run:


start_demo.bat


## Step 4 — Run live trading


start_live.bat


---

# 2. LINUX / MAC INSTALLATION

Run installation script:



chmod +x install_unix.sh
./install_unix.sh


Then:

Demo:


./start_demo.sh


Live:


./start_live.sh


---

# 3. HOW TO GET YOUR RPC API KEY

Recommended: **Helius**
1. Go to https://helius.dev
2. Create account → Create Solana RPC
3. Copy RPC URL
4. Paste into `config.json` → `"rpc": "URL"`

---

# 4. HOW TO GET YOUR PRIVATE KEY (SAFE)

### Phantom:
Settings → Developer Settings → Export Private Key

### Solflare:
Settings → Export Private Key

Paste into:


"private_key": "your_key"


---

# 5. FUNDING YOUR WALLET

Send SOL to your Phantom/Solflare wallet.

The bot uses this SOL for:
- Buying tokens  
- Network fees  

---

# 6. MONITOR THE BOT

### Telegram Alerts  
Add your bot token + chat ID in config.

You will receive:
- New token detected  
- Honeypot skipped  
- Buy executed  
- TP/SL logs  

### VPS Monitoring  
Use SSH from your phone or PC:


screen -r leanbot


---

# 7. WITHDRAW PROFITS

Your bot trades from your Phantom/Solflare wallet.
Withdraw profits by:
- Swapping tokens → SOL  
- Sending SOL → Binance/Coinbase/etc.  
- Cashing out  

---

# 8. SAFETY TIPS

- Keep DRY_RUN = true until comfortable  
- Never share private key  
- Start with small buy-amount  
- Use a VPS for best speed & stability  

---
