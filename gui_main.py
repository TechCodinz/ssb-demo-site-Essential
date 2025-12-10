import subprocess
import threading
import time
import json
import os
import sys
import uuid
import platform
import hashlib
import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests

# ================= PREMIUM THEME COLORS =================
# Matching index.html aesthetics for ultra-premium look
COLORS = {
    "bg_dark": "#020617",        # Deep space blue-black
    "bg_card": "#0f172a",        # Slightly lighter card background
    "bg_input": "#1e293b",       # Input field background
    "accent_cyan": "#22d3ee",    # Primary cyan accent
    "accent_purple": "#a855f7",  # Secondary purple accent
    "accent_orange": "#f97316",  # Tertiary orange accent
    "text_primary": "#f9fafb",   # Bright white text
    "text_muted": "#9ca3af",     # Muted gray text
    "success": "#4ade80",        # Green success
    "danger": "#f97373",         # Red danger
    "warning": "#facc15",        # Yellow warning
    "border": "#334155",         # Border color
}


def setup_premium_theme(root: tk.Tk) -> None:
    """
    Configure a premium dark theme for the entire application.
    Must be called before creating any widgets.
    """
    root.configure(bg=COLORS["bg_dark"])
    
    style = ttk.Style()
    style.theme_use("clam")  # Best base for customization
    
    # Configure root window
    style.configure(".", 
        background=COLORS["bg_dark"],
        foreground=COLORS["text_primary"],
        fieldbackground=COLORS["bg_input"],
        font=("Segoe UI", 10)
    )
    
    # Frame styling
    style.configure("TFrame", background=COLORS["bg_dark"])
    style.configure("Card.TFrame", background=COLORS["bg_card"])
    
    # Label styling
    style.configure("TLabel", 
        background=COLORS["bg_dark"], 
        foreground=COLORS["text_primary"]
    )
    style.configure("Title.TLabel",
        background=COLORS["bg_dark"],
        foreground=COLORS["accent_cyan"],
        font=("Segoe UI", 16, "bold")
    )
    style.configure("Subtitle.TLabel",
        background=COLORS["bg_dark"],
        foreground=COLORS["text_muted"],
        font=("Segoe UI", 10)
    )
    style.configure("Success.TLabel",
        background=COLORS["bg_dark"],
        foreground=COLORS["success"]
    )
    style.configure("Danger.TLabel",
        background=COLORS["bg_dark"],
        foreground=COLORS["danger"]
    )
    style.configure("Accent.TLabel",
        background=COLORS["bg_dark"],
        foreground=COLORS["accent_cyan"],
        font=("Segoe UI", 10, "bold")
    )
    
    # Button styling - Premium gradient look
    style.configure("TButton",
        background=COLORS["bg_input"],
        foreground=COLORS["text_primary"],
        borderwidth=1,
        focuscolor=COLORS["accent_cyan"],
        font=("Segoe UI", 10, "bold"),
        padding=(12, 6)
    )
    style.map("TButton",
        background=[("active", COLORS["accent_cyan"]), ("pressed", COLORS["accent_purple"])],
        foreground=[("active", COLORS["bg_dark"]), ("pressed", COLORS["text_primary"])]
    )
    
    # Primary action button
    style.configure("Primary.TButton",
        background=COLORS["accent_cyan"],
        foreground=COLORS["bg_dark"],
        font=("Segoe UI", 11, "bold"),
        padding=(16, 8)
    )
    style.map("Primary.TButton",
        background=[("active", COLORS["accent_purple"]), ("pressed", "#6366f1")]
    )
    
    # Danger button
    style.configure("Danger.TButton",
        background=COLORS["danger"],
        foreground=COLORS["text_primary"]
    )
    
    # Entry styling
    style.configure("TEntry",
        fieldbackground=COLORS["bg_input"],
        foreground=COLORS["text_primary"],
        insertcolor=COLORS["accent_cyan"],
        borderwidth=1,
        padding=6
    )
    
    # Checkbutton
    style.configure("TCheckbutton",
        background=COLORS["bg_dark"],
        foreground=COLORS["text_primary"]
    )
    
    # LabelFrame styling
    style.configure("TLabelframe",
        background=COLORS["bg_card"],
        foreground=COLORS["accent_cyan"],
        borderwidth=1,
        relief="solid"
    )
    style.configure("TLabelframe.Label",
        background=COLORS["bg_card"],
        foreground=COLORS["accent_cyan"],
        font=("Segoe UI", 10, "bold")
    )


# --------- PATHS & FILES ----------
LOG_FILE = "logs/bot.log"
CONFIG_FILE = "config.json"
LOCAL_LICENSE_FILE = "license.json"

# ✅ Your real GitHub RAW URL
LICENSE_DB_URL = "https://raw.githubusercontent.com/TechCodinz/ssb-license-db/main/licenses.json"

# --------- DEFAULT CONFIG ----------
DEFAULT_CONFIG = {
    "rpc": "https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY",
    "buy_amount_sol": 0.25,
    "min_liquidity_usd": 8000,
    "min_volume_5m": 15000,
    "take_profit_percent": 250,
    "stop_loss_percent": 60,
    "max_trades_per_hour": 12,
    "min_confidence_score": 70.0,
    "max_open_positions": 8,
    "session_start_hour_utc": 0,
    "session_end_hour_utc": 23,
    "telegram_token": "",
    "telegram_chat_id": "",
    "license_file": "",
    "dry_run": True,
}


# ================= HWID & LICENSE HELPERS =================

def get_hwid() -> str:
    """
    Generate a stable HWID for this machine.
    Used to lock license to one PC.
    """
    raw = f"{platform.node()}|{platform.system()}|{platform.machine()}|{uuid.getnode()}"
    hwid = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    return hwid


def load_local_license() -> dict | None:
    if not os.path.exists(LOCAL_LICENSE_FILE):
        return None
    try:
        with open(LOCAL_LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_local_license(data: dict) -> None:
    try:
        with open(LOCAL_LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def is_license_expired(exp_str: str) -> bool:
    """
    Returns True if expiry date is past today.
    Expects YYYY-MM-DD or empty for non-expiring.
    """
    try:
        if not exp_str:
            return False
        exp = datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        return today > exp
    except Exception:
        # if can't parse → treat as expired to be safe
        return True


def fetch_license_db() -> dict | None:
    """
    Fetch the license JSON from your GitHub repo.
    """
    try:
        r = requests.get(LICENSE_DB_URL, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def online_validate_key(key: str) -> dict | None:
    """
    Check the key against the GitHub JSON.
    Returns license record (dict) on success, else None.

    Supports TWO formats:

    1) Array style (your current file):
       {
         "licenses": [
           { "key": "SSB-STD-0001", "plan": "STANDARD", "expires": "2099-12-31", "status": "active" },
           ...
         ]
       }

    2) Dict style (alternative):
       {
         "SSB-STD-0001": { "plan": "STANDARD", "expires": "2099-12-31", "status": "active" },
         "SSB-PRO-0001": { ... }
       }
    """
    db = fetch_license_db()
    if not db:
        return None

    key = key.strip()

    # Format 1: { "licenses": [ {...}, {...} ] }
    if isinstance(db, dict) and isinstance(db.get("licenses"), list):
        for rec in db["licenses"]:
            if not isinstance(rec, dict):
                continue
            if rec.get("key", "").strip() == key:
                return rec

    # Format 2: { "SSB-STD-0001": { ... }, "SSB-PRO-0001": { ... } }
    if isinstance(db, dict) and "licenses" not in db:
        for k, rec in db.items():
            if not isinstance(rec, dict):
                continue
            rec_key = rec.get("key", "") or k
            if str(rec_key).strip() == key:
                # normalize to have "key" inside too
                rec = rec.copy()
                rec["key"] = str(rec_key).strip()
                return rec

    return None


def verify_or_prompt_license(root: tk.Tk) -> bool:
    """
    - Check local license.json
    - If invalid/expired/missing → show activation window.
    - Returns True if license is valid, False to quit app.
    """
    current_hwid = get_hwid()
    local_lic = load_local_license()

    # ---- Try using existing local license ----
    if local_lic:
        saved_key = local_lic.get("key", "").strip()
        saved_hwid = local_lic.get("hwid", "*")
        expires = local_lic.get("expires", "")
        status = local_lic.get("status", "active")

        if status != "active":
            # Already marked as revoked locally
            messagebox.showerror(
                "License revoked",
                "Your license has been revoked. Please contact support."
            )
            return False

        if is_license_expired(expires):
            messagebox.showerror(
                "License expired",
                f"Your license expired on {expires}. Please renew to continue using SSB."
            )
            return False

        # HWID check (unless '*' for unlimited devices)
        if saved_hwid not in ("*", current_hwid):
            messagebox.showerror(
                "HWID mismatch",
                "This license is locked to a different machine.\n"
                "Please contact support if you changed your PC."
            )
            return False

        # Optional online re-check (for revocations / upgrades)
        rec = online_validate_key(saved_key)
        if rec:
            if rec.get("status", "active") != "active":
                messagebox.showerror(
                    "License revoked",
                    "Your license has been revoked. Please contact support."
                )
                local_lic["status"] = "revoked"
                save_local_license(local_lic)
                return False
            # Refresh expiry/plan from server
            local_lic["expires"] = rec.get("expires", expires)
            local_lic["plan"] = rec.get("plan", local_lic.get("plan", "UNKNOWN"))
            local_lic["status"] = rec.get("status", "active")
            srv_hwid = rec.get("hwid", saved_hwid)
            local_lic["hwid"] = srv_hwid
            save_local_license(local_lic)
            return True
        else:
            # No internet / server down → allow if not expired and HWID matches
            return True

    # ---- No valid license locally → show activation UI ----
    win = ActivationWindow(root)
    root.wait_window(win)
    return win.success


# ================= ACTIVATION WINDOW =================

class ActivationWindow(tk.Toplevel):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.title("Sol Sniper Bot PRO – Activation")
        self.geometry("500x480")
        self.minsize(480, 450)
        self.resizable(False, False)
        self.success = False
        self.demo_mode = False
        self.configure(bg=COLORS["bg_dark"])

        self.hwid = get_hwid()

        self.create_widgets()
        
        # Center window on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.winfo_screenheight() // 2) - (480 // 2)
        self.geometry(f"500x480+{x}+{y}")

    def create_widgets(self):
        # ===== BOTTOM BUTTONS (pack first with side=BOTTOM) =====
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="bottom", fill="x", padx=20, pady=15)
        
        # Try Demo button - prominent
        demo_btn = ttk.Button(
            btn_frame, 
            text="🎮 Try Free Demo", 
            command=self.start_demo,
            style="Primary.TButton"
        )
        demo_btn.pack(side="left", padx=(0, 10))
        
        activate_btn = ttk.Button(
            btn_frame, 
            text="✓ Activate License", 
            command=self.activate
        )
        activate_btn.pack(side="left", padx=(0, 10))
        
        cancel_btn = ttk.Button(btn_frame, text="Exit", command=self.on_cancel)
        cancel_btn.pack(side="left")
        
        # ===== SEPARATOR =====
        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(side="bottom", fill="x", padx=20)
        
        # ===== DEMO INFO BOX =====
        demo_info = ttk.Frame(self, padding=10)
        demo_info.pack(side="bottom", fill="x", padx=20, pady=(0, 5))
        
        demo_label = ttk.Label(
            demo_info,
            text="💡 Try DRY RUN mode FREE! See the bot in action without risking real funds.\n"
                 "   Purchase a license to unlock LIVE trading mode.",
            font=("Segoe UI", 9),
            foreground=COLORS["warning"],
            justify="left"
        )
        demo_label.pack(anchor="w")

        # ===== MAIN CONTENT (fills remaining space) =====
        content = ttk.Frame(self, padding=20)
        content.pack(side="top", fill="both", expand=True)

        # Title
        title = ttk.Label(
            content,
            text="Sol Sniper Bot PRO",
            font=("Segoe UI", 16, "bold"),
            foreground=COLORS["accent_cyan"]
        )
        title.pack(pady=(0, 5))

        subtitle = ttk.Label(
            content,
            text="Enter your license key or try the free demo",
            font=("Segoe UI", 10),
            foreground=COLORS["text_muted"]
        )
        subtitle.pack(pady=(0, 20))

        # HWID Row (horizontal layout)
        hwid_row = ttk.Frame(content)
        hwid_row.pack(fill="x", pady=(0, 15))
        
        hwid_lbl = ttk.Label(hwid_row, text="Your HWID:", width=12)
        hwid_lbl.pack(side="left")
        
        self.hwid_entry = ttk.Entry(hwid_row, width=20)
        self.hwid_entry.insert(0, self.hwid)
        self.hwid_entry.configure(state="readonly")
        self.hwid_entry.pack(side="left", padx=(0, 10))
        
        copy_btn = ttk.Button(hwid_row, text="📋 Copy", command=self.copy_hwid, width=8)
        copy_btn.pack(side="left")

        # License Key Row
        lic_row = ttk.Frame(content)
        lic_row.pack(fill="x", pady=(0, 15))
        
        lic_lbl = ttk.Label(lic_row, text="License Key:", width=12)
        lic_lbl.pack(side="left")
        
        self.lic_var = tk.StringVar()
        self.lic_entry = ttk.Entry(lic_row, textvariable=self.lic_var)
        self.lic_entry.pack(side="left", fill="x", expand=True)

        # Email Row
        email_row = ttk.Frame(content)
        email_row.pack(fill="x", pady=(0, 10))
        
        email_lbl = ttk.Label(email_row, text="Email:", width=12)
        email_lbl.pack(side="left")
        
        self.email_var = tk.StringVar()
        email_entry = ttk.Entry(email_row, textvariable=self.email_var)
        email_entry.pack(side="left", fill="x", expand=True)
        
        email_hint = ttk.Label(
            content,
            text="(Optional - for support contact)",
            font=("Segoe UI", 8),
            foreground=COLORS["text_muted"]
        )
        email_hint.pack(anchor="e")
    
    def start_demo(self):
        """Start in demo/DRY RUN mode without license"""
        # Save a demo license locally
        demo_lic = {
            "key": "DEMO-MODE",
            "hwid": self.hwid,
            "expires": "",
            "plan": "DEMO",
            "email": "",
            "status": "demo",
            "activated_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        save_local_license(demo_lic)
        
        # Force DRY RUN in config
        cfg = load_config()
        cfg["dry_run"] = True
        save_config(cfg)
        
        messagebox.showinfo(
            "Demo Mode",
            "🎮 Demo Mode Activated!\n\n"
            "You can now use DRY RUN mode to see the bot in action.\n"
            "No real trades will be made.\n\n"
            "To unlock LIVE trading, purchase a license!"
        )
        self.success = True
        self.demo_mode = True
        self.destroy()

    def copy_hwid(self):
        self.clipboard_clear()
        self.clipboard_append(self.hwid)
        messagebox.showinfo("Copied", "HWID copied to clipboard.")

    def activate(self):
        key = self.lic_var.get().strip()
        if not key:
            messagebox.showerror("Error", "Please enter your license key.")
            return

        # Online validation
        rec = online_validate_key(key)
        if not rec:
            messagebox.showerror(
                "Invalid key",
                "License key not found. Please check and try again.\n\n"
                "If you just purchased, wait 1–2 minutes or contact support."
            )
            return

        status = rec.get("status", "active")
        expires = rec.get("expires", "")
        plan = rec.get("plan", "UNKNOWN")
        srv_hwid = rec.get("hwid", "*")

        if status != "active":
            messagebox.showerror(
                "License inactive",
                f"Your license status is: {status}. Please contact support."
            )
            return

        if is_license_expired(expires):
            messagebox.showerror(
                "License expired",
                f"Your license expired on {expires}. Please renew to continue using SSB."
            )
            return

        # HWID check (if not wildcard)
        current_hwid = self.hwid
        if srv_hwid not in ("*", current_hwid):
            messagebox.showerror(
                "HWID mismatch",
                "This license is locked to a different machine.\n"
                "Please contact support if you changed your PC."
            )
            return

        # Save locally, lock to HWID (store actual HWID if wildcard)
        lic_data = {
            "key": key,
            "hwid": srv_hwid if srv_hwid != "*" else current_hwid,
            "expires": expires,
            "plan": plan,
            "email": self.email_var.get().strip(),
            "status": status,
            "activated_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        save_local_license(lic_data)

        messagebox.showinfo(
            "Activated",
            f"Sol Sniper Bot PRO activated!\n\nPlan: {plan}\nExpires: {expires or 'No expiry'}"
        )
        self.success = True
        self.destroy()

    def on_cancel(self):
        self.success = False
        self.destroy()


# ================= CONFIG HELPERS =================

def load_config() -> dict:
    """
    Load config.json, auto-create with defaults if missing,
    and ensure all required keys exist.
    """
    cfg: dict = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                cfg = {}
        except Exception:
            cfg = {}

    # If still empty → init with defaults
    if not cfg:
        cfg = DEFAULT_CONFIG.copy()
        save_config(cfg)
        return cfg

    # Ensure all default keys exist
    changed = False
    for k, v in DEFAULT_CONFIG.items():
        if k not in cfg:
            cfg[k] = v
            changed = True

    if changed:
        save_config(cfg)

    return cfg


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ================= CONFIG EDITOR WINDOW =================

class ConfigEditorWindow(tk.Toplevel):
    """
    Simple config editor for config.json
    """
    def __init__(self, master, on_saved_callback=None):
        super().__init__(master)
        self.title("Sol Sniper Bot PRO – Config Editor")
        self.geometry("520x560")
        self.resizable(False, False)
        self.on_saved_callback = on_saved_callback

        self.cfg = load_config()
        self.entries = {}

        lic = load_local_license() or {}
        self.plan = (lic.get("plan") or "STANDARD").upper()

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(
            frame,
            text=f"Edit Bot Settings ({self.plan})",
            font=("Segoe UI", 12, "bold")
        )
        title.pack(pady=(0, 6))

        subtitle_text = {
            "STANDARD": "STANDARD: DRY RUN only. Advanced controls locked.",
            "PRO": "PRO: Full live-trading controls unlocked.",
            "ELITE": "ELITE: Full controls + priority tier."
        }.get(self.plan, self.plan)

        subtitle = ttk.Label(frame, text=subtitle_text, font=("Segoe UI", 9))
        subtitle.pack(pady=(0, 8))

        form = ttk.Frame(frame)
        form.pack(fill="both", expand=True)

        # Fields: label, key, type
        fields = [
            ("RPC URL", "rpc", str),
            ("Buy amount (SOL)", "buy_amount_sol", float),
            ("Min liquidity (USD)", "min_liquidity_usd", float),
            ("Min volume 5m (USD)", "min_volume_5m", float),
            ("Take profit (%)", "take_profit_percent", float),
            ("Stop loss (%)", "stop_loss_percent", float),
            ("Max trades per hour", "max_trades_per_hour", int),
            ("Min confidence score", "min_confidence_score", float),
            ("Max open positions", "max_open_positions", int),
            ("Session start hour (UTC)", "session_start_hour_utc", int),
            ("Session end hour (UTC)", "session_end_hour_utc", int),
            ("Telegram bot token", "telegram_token", str),
            ("Telegram chat ID", "telegram_chat_id", str),
            ("License file (.ssb, optional)", "license_file", str),
        ]

        for label_text, key, _typ in fields:
            row = ttk.Frame(form)
            row.pack(fill="x", pady=3)

            lbl = ttk.Label(row, text=label_text + ":", width=24, anchor="w")
            lbl.pack(side="left")

            val = self.cfg.get(key, DEFAULT_CONFIG.get(key, ""))
            entry = ttk.Entry(row)
            entry.insert(0, str(val))
            entry.pack(side="left", fill="x", expand=True)
            self.entries[key] = (entry, _typ)

        # Dry run checkbox
        chk_frame = ttk.Frame(frame)
        chk_frame.pack(fill="x", pady=(8, 4))
        self.dry_run_var = tk.BooleanVar(value=self.cfg.get("dry_run", True))
        self.dry_chk = ttk.Checkbutton(
            chk_frame,
            text="DRY RUN mode (no real trades)",
            variable=self.dry_run_var
        )
        self.dry_chk.pack(anchor="w")

        # Lock / disable for STANDARD plan (Option 2: show but disable)
        if self.plan == "STANDARD":
            # Enforce DRY RUN
            self.dry_run_var.set(True)
            self.dry_chk.configure(state="disabled")

            advanced_keys = [
                "buy_amount_sol",
                "min_liquidity_usd",
                "min_volume_5m",
                "take_profit_percent",
                "stop_loss_percent",
                "max_trades_per_hour",
                "min_confidence_score",
                "max_open_positions",
                "session_start_hour_utc",
                "session_end_hour_utc",
            ]
            for k in advanced_keys:
                entry, _ = self.entries.get(k, (None, None))
                if entry is not None:
                    entry.configure(state="disabled")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(12, 0))

        save_btn = ttk.Button(btn_frame, text="Save Config", command=self.save_config)
        save_btn.pack(side="left")

        close_btn = ttk.Button(btn_frame, text="Close", command=self.destroy)
        close_btn.pack(side="right")

    def save_config(self):
        new_cfg = load_config()

        # Validate & convert numeric fields
        for key, (entry, _typ) in self.entries.items():
            # If disabled for STANDARD, keep existing value
            if self.plan == "STANDARD" and str(entry.cget("state")) == "disabled":
                continue

            raw = entry.get().strip()
            if _typ in (int, float):
                if raw == "":
                    messagebox.showerror("Error", f"{key} cannot be empty.")
                    return
                try:
                    val = _typ(raw)
                except ValueError:
                    messagebox.showerror("Error", f"{key} must be a valid {_typ.__name__}.")
                    return
            else:
                val = raw
            new_cfg[key] = val

        # DRY RUN: forced true for STANDARD
        if self.plan == "STANDARD":
            new_cfg["dry_run"] = True
        else:
            new_cfg["dry_run"] = bool(self.dry_run_var.get())

        try:
            save_config(new_cfg)
            messagebox.showinfo("Saved", "Configuration saved successfully.")
            if self.on_saved_callback:
                self.on_saved_callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config:\n{e}")


# ================= MAIN BOT GUI =================

class BotGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sol Sniper Bot PRO – Control Panel")
        self.geometry("1000x700")
        self.minsize(900, 600)

        # Apply premium dark theme
        setup_premium_theme(self)

        self.bot_process = None
        self.stop_log = False

        # License check before showing main UI
        ok = verify_or_prompt_license(self)
        if not ok:
            # User closed / failed activation
            self.destroy()
            return

        self.create_widgets()
        self.update_config_labels()
        self.start_log_tail_thread()

    def create_widgets(self):
        # ===== HEADER SECTION =====
        header_frame = tk.Frame(self, bg=COLORS["bg_card"], height=70)
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Brand logo placeholder
        logo_frame = tk.Frame(header_frame, bg=COLORS["accent_cyan"], width=50, height=50)
        logo_frame.pack(side="left", padx=15, pady=10)
        logo_frame.pack_propagate(False)
        logo_label = tk.Label(logo_frame, text="SSB", font=("Segoe UI", 14, "bold"), 
                              bg=COLORS["accent_cyan"], fg=COLORS["bg_dark"])
        logo_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Brand text
        brand_frame = tk.Frame(header_frame, bg=COLORS["bg_card"])
        brand_frame.pack(side="left", padx=5, pady=10)
        brand_title = tk.Label(brand_frame, text="Sol Sniper Bot PRO", 
                               font=("Segoe UI", 16, "bold"),
                               bg=COLORS["bg_card"], fg=COLORS["text_primary"])
        brand_title.pack(anchor="w")
        brand_sub = tk.Label(brand_frame, text="SOLANA PUMP.FUN SNIPER ENGINE", 
                             font=("Segoe UI", 8),
                             bg=COLORS["bg_card"], fg=COLORS["text_muted"])
        brand_sub.pack(anchor="w")
        
        # Status indicators on right
        status_frame = tk.Frame(header_frame, bg=COLORS["bg_card"])
        status_frame.pack(side="right", padx=15, pady=10)
        
        self.mode_label = tk.Label(status_frame, text="Mode: ?", 
                                   font=("Segoe UI", 10, "bold"),
                                   bg=COLORS["bg_card"], fg=COLORS["accent_cyan"])
        self.mode_label.pack(anchor="e")
        
        self.plan_label = tk.Label(status_frame, text="Plan: ?", 
                                   font=("Segoe UI", 9),
                                   bg=COLORS["bg_card"], fg=COLORS["text_muted"])
        self.plan_label.pack(anchor="e")

        # ===== TOOLBAR =====
        btn_frame = tk.Frame(self, bg=COLORS["bg_dark"])
        btn_frame.pack(fill="x", padx=15, pady=10)

        self.start_btn = ttk.Button(btn_frame, text="▶ Start Bot", 
                                    command=self.start_bot, style="Primary.TButton")
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ttk.Button(btn_frame, text="⬛ Stop Bot", 
                                   command=self.stop_bot, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 10))

        self.edit_cfg_btn = ttk.Button(btn_frame, text="⚙ Edit Config", 
                                       command=self.open_config_editor)
        self.edit_cfg_btn.pack(side="left", padx=(0, 10))

        self.refresh_btn = ttk.Button(btn_frame, text="🔄 Reload", 
                                      command=self.update_config_labels)
        self.refresh_btn.pack(side="left")
        
        # RPC label on right side of toolbar
        self.rpc_label = tk.Label(btn_frame, text="RPC: ?", 
                                  font=("Segoe UI", 9),
                                  bg=COLORS["bg_dark"], fg=COLORS["text_muted"])
        self.rpc_label.pack(side="right")

        # ===== LOG VIEW =====
        log_frame = ttk.LabelFrame(self, text="📊 Live Trading Log")
        log_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            state="disabled", 
            wrap="word", 
            font=("Consolas", 10),
            bg=COLORS["bg_dark"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["accent_cyan"],
            selectbackground=COLORS["accent_purple"],
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent_cyan"]
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Configure log text tags for colored output
        self.log_text.tag_configure("success", foreground=COLORS["success"])
        self.log_text.tag_configure("danger", foreground=COLORS["danger"])
        self.log_text.tag_configure("warning", foreground=COLORS["warning"])
        self.log_text.tag_configure("info", foreground=COLORS["accent_cyan"])

        # ===== STATUS BAR =====
        status_bar_frame = tk.Frame(self, bg=COLORS["bg_card"], height=30)
        status_bar_frame.pack(fill="x", side="bottom")
        status_bar_frame.pack_propagate(False)
        
        self.status_var = tk.StringVar(value="✨ Ready to dominate the market.")
        status_label = tk.Label(status_bar_frame, textvariable=self.status_var,
                               font=("Segoe UI", 9),
                               bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                               anchor="w", padx=15)
        status_label.pack(fill="x", pady=5)

    def update_config_labels(self):
        cfg = load_config()
        lic = load_local_license() or {}
        plan = (lic.get("plan") or "STANDARD").upper()
        exp = lic.get("expires", "") or "No expiry"

        # Enforce DRY RUN for STANDARD plan
        if plan == "STANDARD":
            if not cfg.get("dry_run", True):
                cfg["dry_run"] = True
                save_config(cfg)
            mode = "DRY RUN (STANDARD)"
        else:
            mode = "DRY RUN" if cfg.get("dry_run", True) else "LIVE"

        rpc = cfg.get("rpc", "N/A")

        self.mode_label.config(text=f"Mode: {mode}")
        self.rpc_label.config(text=f"RPC: {rpc}")
        self.plan_label.config(text=f"Plan: {plan} | Expires: {exp}")

        self.status_var.set("Config & license loaded.")

    def open_config_editor(self):
        ConfigEditorWindow(self, on_saved_callback=self.update_config_labels)

    def start_bot(self):
        if self.bot_process is not None:
            messagebox.showinfo("Already running", "Bot is already running.")
            return

        # Clear log file
        os.makedirs("logs", exist_ok=True)
        try:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

        self.status_var.set("Starting bot...")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        def run_bot():
            try:
                # Decide how to start bot depending on environment
                if getattr(sys, "frozen", False):
                    # Running as PyInstaller EXE → expect ssb_core.exe in same folder
                    exe_dir = os.path.dirname(sys.executable)
                    core_exe = os.path.join(exe_dir, "ssb_core.exe")
                    if not os.path.exists(core_exe):
                        self.status_var.set("ERROR: ssb_core.exe not found next to GUI.")
                        messagebox.showerror(
                            "Core bot missing",
                            "ssb_core.exe not found in the same folder as the GUI.\n\n"
                            "Place ssb_core.exe next to gui_main.exe."
                        )
                        self.start_btn.config(state="normal")
                        self.stop_btn.config(state="disabled")
                        return
                    cmd = [core_exe]
                else:
                    # Dev mode: run main.py with current Python
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    main_py = os.path.join(script_dir, "main.py")
                    if not os.path.exists(main_py):
                        self.status_var.set("ERROR: main.py not found.")
                        messagebox.showerror(
                            "main.py missing",
                            "main.py not found in this folder.\n\n"
                            "Make sure gui_main.py and main.py stay together."
                        )
                        self.start_btn.config(state="normal")
                        self.stop_btn.config(state="disabled")
                        return
                    cmd = [sys.executable, main_py]

                self.bot_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.status_var.set("Bot running.")
            except Exception as e:
                self.status_var.set(f"Failed to start bot: {e}")
                messagebox.showerror("Error", f"Failed to start bot:\n{e}")
                self.start_btn.config(state="normal")
                self.stop_btn.config(state="disabled")

        threading.Thread(target=run_bot, daemon=True).start()

    def stop_bot(self):
        if self.bot_process is not None:
            try:
                self.bot_process.terminate()
            except Exception:
                pass
            self.bot_process = None
            self.status_var.set("Bot stopped.")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def start_log_tail_thread(self):
        def tail_log():
            last_size = 0
            while not self.stop_log:
                try:
                    if os.path.exists(LOG_FILE):
                        size = os.path.getsize(LOG_FILE)
                        if size > last_size:
                            with open(LOG_FILE, "r", encoding="utf-8") as f:
                                f.seek(last_size)
                                new_data = f.read()
                                if new_data:
                                    self.append_log(new_data)
                                last_size = size
                except Exception:
                    pass
                time.sleep(0.8)

        threading.Thread(target=tail_log, daemon=True).start()

    def append_log(self, text):
        """Append log text with color coding based on content."""
        self.log_text.configure(state="normal")
        
        # Process each line for coloring
        for line in text.splitlines(keepends=True):
            tag = None
            line_lower = line.lower()
            
            # GREEN: New tokens, buys, take-profit, success
            if any(kw in line_lower for kw in ["new token", "🚀", "buy", "tp", "take profit", "success", "connected", "subscribed"]):
                tag = "success"
            # RED: Errors, stop-loss, failed, rejected
            elif any(kw in line_lower for kw in ["error", "❌", "sl", "stop loss", "failed", "rejected", "freeze_auth"]):
                tag = "danger"
            # YELLOW: Warnings, retrying, waiting
            elif any(kw in line_lower for kw in ["warning", "⚠", "retry", "waiting", "no pairs"]):
                tag = "warning"
            # CYAN: Risk analysis, engine info, stats
            elif any(kw in line_lower for kw in ["risk", "📊", "engine", "stats", "ultra features", "conf"]):
                tag = "info"
            
            if tag:
                self.log_text.insert("end", line, tag)
            else:
                self.log_text.insert("end", line)
        
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_close(self):
        self.stop_log = True
        if self.bot_process is not None:
            try:
                self.bot_process.terminate()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = BotGUI()
    # If activation failed, app may already be destroyed
    try:
        app.protocol("WM_DELETE_WINDOW", app.on_close)
        app.mainloop()
    except Exception:
        pass
