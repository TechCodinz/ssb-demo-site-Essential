"""
Sol Sniper Bot PRO - Telegram Order Database
SQLite storage for order tracking
"""
import aiosqlite
import os
import uuid
import random
import string
from datetime import datetime
from typing import Optional, Dict, List, Any

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "orders.db")


async def init_db():
    """Initialize the database with required tables"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                order_ref TEXT UNIQUE NOT NULL,
                telegram_id TEXT NOT NULL,
                telegram_username TEXT,
                email TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                plan_type TEXT NOT NULL,
                amount_usdt REAL NOT NULL,
                tx_hash TEXT,
                note TEXT,
                status TEXT DEFAULT 'pending',
                license_key TEXT,
                created_at TEXT NOT NULL,
                approved_at TEXT,
                approved_by TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id TEXT PRIMARY KEY,
                telegram_id TEXT NOT NULL,
                message_type TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_telegram_id ON orders(telegram_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_ref ON orders(order_ref)
        """)
        
        await db.commit()


def generate_order_ref() -> str:
    """Generate a unique order reference like TG-ABC123XYZ"""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=10))
    return f"TG-{suffix}"


async def create_order(
    telegram_id: str,
    telegram_username: Optional[str],
    email: str,
    plan_id: str,
    plan_type: str,
    amount_usdt: float,
    tx_hash: Optional[str] = None,
    note: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new order in the database"""
    order_id = str(uuid.uuid4())
    order_ref = generate_order_ref()
    created_at = datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO orders (
                id, order_ref, telegram_id, telegram_username, email,
                plan_id, plan_type, amount_usdt, tx_hash, note, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            order_id, order_ref, telegram_id, telegram_username,
            email, plan_id, plan_type, amount_usdt, tx_hash, note, created_at
        ))
        await db.commit()
    
    return {
        "id": order_id,
        "order_ref": order_ref,
        "telegram_id": telegram_id,
        "telegram_username": telegram_username,
        "email": email,
        "plan_id": plan_id,
        "plan_type": plan_type,
        "amount_usdt": amount_usdt,
        "tx_hash": tx_hash,
        "note": note,
        "status": "pending",
        "created_at": created_at,
    }


async def update_order_tx(order_ref: str, tx_hash: str) -> bool:
    """Update order with TX hash"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE orders SET tx_hash = ? WHERE order_ref = ?",
            (tx_hash, order_ref)
        )
        await db.commit()
        return cursor.rowcount > 0


async def approve_order(order_ref: str, approved_by: str, license_key: str) -> bool:
    """Mark order as approved and add license key"""
    approved_at = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            UPDATE orders 
            SET status = 'approved', approved_at = ?, approved_by = ?, license_key = ?
            WHERE order_ref = ?
        """, (approved_at, approved_by, license_key, order_ref))
        await db.commit()
        return cursor.rowcount > 0


async def reject_order(order_ref: str, rejected_by: str) -> bool:
    """Mark order as rejected"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            UPDATE orders 
            SET status = 'rejected', approved_by = ?
            WHERE order_ref = ?
        """, (rejected_by, order_ref))
        await db.commit()
        return cursor.rowcount > 0


async def get_order_by_ref(order_ref: str) -> Optional[Dict[str, Any]]:
    """Get order by reference code"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE order_ref = ?", (order_ref,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def get_pending_orders() -> List[Dict[str, Any]]:
    """Get all pending orders"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_orders_by_telegram_id(telegram_id: str) -> List[Dict[str, Any]]:
    """Get all orders for a specific Telegram user"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE telegram_id = ? ORDER BY created_at DESC",
            (telegram_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_sales_stats() -> Dict[str, Any]:
    """Get sales statistics"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Total sales
        cursor = await db.execute(
            "SELECT SUM(amount_usdt) as total FROM orders WHERE status = 'approved'"
        )
        row = await cursor.fetchone()
        total_sales = row[0] or 0
        
        # Sales by plan
        cursor = await db.execute("""
            SELECT plan_id, COUNT(*) as count, SUM(amount_usdt) as total
            FROM orders WHERE status = 'approved'
            GROUP BY plan_id
        """)
        plan_rows = await cursor.fetchall()
        sales_by_plan = {row[0]: {"count": row[1], "total": row[2]} for row in plan_rows}
        
        # Order counts
        cursor = await db.execute(
            "SELECT status, COUNT(*) FROM orders GROUP BY status"
        )
        status_rows = await cursor.fetchall()
        orders_by_status = {row[0]: row[1] for row in status_rows}
        
        return {
            "total_sales_usdt": total_sales,
            "sales_by_plan": sales_by_plan,
            "orders_by_status": orders_by_status,
        }


async def schedule_message(
    telegram_id: str,
    message_type: str,
    scheduled_for: datetime
) -> str:
    """Schedule a marketing message"""
    msg_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO scheduled_messages (id, telegram_id, message_type, scheduled_for, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (msg_id, telegram_id, message_type, scheduled_for.isoformat(), created_at))
        await db.commit()
    
    return msg_id


async def get_due_messages() -> List[Dict[str, Any]]:
    """Get messages that are due to be sent"""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM scheduled_messages 
            WHERE sent = 0 AND scheduled_for <= ?
        """, (now,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_message_sent(msg_id: str) -> None:
    """Mark a scheduled message as sent"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE scheduled_messages SET sent = 1 WHERE id = ?",
            (msg_id,)
        )
        await db.commit()
