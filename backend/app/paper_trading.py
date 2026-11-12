"""SQLite paper-trading ledger. Simulated fills only; never connects to a broker."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


def _init(connection: sqlite3.Connection, initial_capital: float) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS paper_account (
        id INTEGER PRIMARY KEY CHECK(id=1), initial_capital REAL NOT NULL,
        cash REAL NOT NULL, realized_pnl REAL NOT NULL DEFAULT 0)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS paper_positions (
        symbol TEXT PRIMARY KEY, quantity INTEGER NOT NULL CHECK(quantity>=0),
        average_price REAL NOT NULL CHECK(average_price>=0), updated_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS paper_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, side TEXT NOT NULL,
        quantity INTEGER NOT NULL, fill_price REAL NOT NULL, gross_value REAL NOT NULL,
        realized_pnl REAL NOT NULL, created_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '')""")
    connection.execute(
        "INSERT OR IGNORE INTO paper_account(id,initial_capital,cash,realized_pnl) VALUES(1,?,?,0)",
        (initial_capital, initial_capital),
    )


def place_paper_order(database_path: str | Path, symbol: str, side: str, quantity: int,
                      fill_price: float, initial_capital: float = 1_000_000,
                      note: str = "") -> dict:
    """Execute a simulated cash-equity buy/sell at a user-supplied assumed fill price."""
    normalized = symbol.strip().upper()
    direction = side.strip().lower()
    if not normalized or direction not in {"buy", "sell"}:
        raise ValueError("A symbol and side buy/sell are required.")
    if quantity <= 0 or fill_price <= 0 or initial_capital <= 0:
        raise ValueError("Quantity, fill price, and initial capital must be positive.")
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database_path, timeout=30) as db:
        db.row_factory = sqlite3.Row
        _init(db, initial_capital)
        account = db.execute("SELECT * FROM paper_account WHERE id=1").fetchone()
        position = db.execute("SELECT * FROM paper_positions WHERE symbol=?", (normalized,)).fetchone()
        old_qty = int(position["quantity"]) if position else 0
        old_avg = float(position["average_price"]) if position else 0.0
        gross = quantity * fill_price
        realized = 0.0
        cash = float(account["cash"])
        if direction == "buy":
            if gross > cash:
                raise ValueError(f"Insufficient paper cash: available {cash:.2f}, required {gross:.2f}.")
            new_qty = old_qty + quantity
            new_avg = ((old_qty * old_avg) + gross) / new_qty
            cash -= gross
        else:
            if quantity > old_qty:
                raise ValueError(f"Cannot sell {quantity}; paper position has only {old_qty} shares.")
            new_qty = old_qty - quantity
            new_avg = old_avg if new_qty else 0.0
            realized = (fill_price - old_avg) * quantity
            cash += gross
        db.execute("UPDATE paper_account SET cash=?, realized_pnl=realized_pnl+? WHERE id=1", (cash, realized))
        db.execute(
            "INSERT INTO paper_positions(symbol,quantity,average_price,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity,average_price=excluded.average_price,updated_at=excluded.updated_at",
            (normalized, new_qty, new_avg, now),
        )
        cursor = db.execute(
            "INSERT INTO paper_orders(symbol,side,quantity,fill_price,gross_value,realized_pnl,created_at,note) VALUES(?,?,?,?,?,?,?,?)",
            (normalized, direction, quantity, fill_price, gross, realized, now, note),
        )
        return {"order_id": cursor.lastrowid, "symbol": normalized, "side": direction,
                "quantity": quantity, "assumed_fill_price": fill_price, "gross_value": round(gross, 2),
                "realized_pnl": round(realized, 2), "remaining_quantity": new_qty,
                "cash_balance": round(cash, 2), "fill_type": "simulated_user_supplied_price",
                "warning": "Paper fill only. Brokerage, taxes, slippage, partial fills and market impact are not modeled."}


def get_paper_portfolio(database_path: str | Path, initial_capital: float = 1_000_000) -> dict:
    with sqlite3.connect(database_path, timeout=30) as db:
        db.row_factory = sqlite3.Row
        _init(db, initial_capital)
        account = db.execute("SELECT * FROM paper_account WHERE id=1").fetchone()
        positions = [dict(row) for row in db.execute(
            "SELECT symbol,quantity,average_price,updated_at FROM paper_positions WHERE quantity>0 ORDER BY symbol"
        )]
        orders = [dict(row) for row in db.execute(
            "SELECT id,symbol,side,quantity,fill_price,gross_value,realized_pnl,created_at,note FROM paper_orders ORDER BY id DESC LIMIT 100"
        )]
    return {"initial_capital": account["initial_capital"], "cash": round(account["cash"], 2),
            "realized_pnl": round(account["realized_pnl"], 2), "open_positions": positions,
            "recent_orders": orders, "open_position_count": len(positions),
            "warning": "Paper ledger only. Holdings are not marked to market; fills are assumed at user-entered prices and exclude fees/slippage."}
