"""
Sprint 4: Trade Logging Database Module
SQLite + aiosqlite for async I/O with FastAPI
"""
import aiosqlite
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import config

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════════

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    symbol      TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    price       REAL,
    quote_qty   REAL,
    source_ip   TEXT,
    payload     TEXT,
    processed   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trades (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id      INTEGER NOT NULL REFERENCES signals(id),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    symbol         TEXT    NOT NULL,
    side           TEXT    NOT NULL,
    order_id       TEXT,
    status         TEXT,
    requested_qty  REAL,
    executed_qty   REAL,
    executed_price REAL,
    commission     REAL,
    error_message  TEXT,
    pnl            REAL
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol  ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_trades_symbol   ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_signal   ON trades(signal_id);

CREATE TABLE IF NOT EXISTS briefs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    symbols_scanned INTEGER,
    scan_data       TEXT,
    ai_analysis     TEXT,
    vision_data     TEXT,
    screenshot      TEXT,
    brief_text      TEXT,
    success         INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_briefs_created ON briefs(created_at);
"""


# ═══════════════════════════════════════════════════════════════
# INIT
# ═══════════════════════════════════════════════════════════════

async def init_db():
    """Tao bang khi khoi dong server."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()
    log.info(f"Database initialized: {config.DB_PATH}")


# ═══════════════════════════════════════════════════════════════
# SIGNAL CRUD
# ═══════════════════════════════════════════════════════════════

async def insert_signal(
    symbol: str,
    action: str,
    price: Optional[float] = None,
    quote_qty: Optional[float] = None,
    source_ip: Optional[str] = None,
    payload: Optional[Dict] = None,
) -> int:
    """Luu tin hieu moi tu TradingView, tra ve signal_id."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO signals (symbol, action, price, quote_qty, source_ip, payload)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol, action, price, quote_qty, source_ip, json.dumps(payload) if payload else None),
        )
        await db.commit()
        signal_id = cursor.lastrowid
        log.info(f"Signal #{signal_id} saved: {action} {symbol}")
        return signal_id


async def update_signal_status(signal_id: int, processed: int):
    """Cap nhat trang thai signal: 0=pending, 1=success, 2=failed."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE signals SET processed = ? WHERE id = ?",
            (processed, signal_id),
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════
# TRADE CRUD
# ═══════════════════════════════════════════════════════════════

async def insert_trade(
    signal_id: int,
    symbol: str,
    side: str,
    order_id: Optional[str] = None,
    status: Optional[str] = None,
    requested_qty: Optional[float] = None,
    executed_qty: Optional[float] = None,
    executed_price: Optional[float] = None,
    commission: Optional[float] = None,
    error_message: Optional[str] = None,
    pnl: Optional[float] = None,
) -> int:
    """Luu ket qua giao dich Binance."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO trades
               (signal_id, symbol, side, order_id, status,
                requested_qty, executed_qty, executed_price,
                commission, error_message, pnl)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (signal_id, symbol, side, order_id, status,
             requested_qty, executed_qty, executed_price,
             commission, error_message, pnl),
        )
        await db.commit()
        trade_id = cursor.lastrowid
        log.info(f"Trade #{trade_id} saved: {side} {symbol} (signal #{signal_id})")
        return trade_id


# ═══════════════════════════════════════════════════════════════
# QUERY — TRADE HISTORY
# ═══════════════════════════════════════════════════════════════

async def get_trades(
    symbol: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Truy van lich su giao dich voi pagination va filter."""
    conditions = []
    params: list = []

    if symbol:
        conditions.append("t.symbol = ?")
        params.append(symbol.upper())
    if from_date:
        conditions.append("t.created_at >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("t.created_at <= ?")
        params.append(to_date)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Count total
        row = await db.execute_fetchall(
            f"SELECT COUNT(*) as cnt FROM trades t {where}", params
        )
        total = row[0][0] if row else 0

        # Fetch page
        limit = min(limit, 200)
        rows = await db.execute_fetchall(
            f"""SELECT t.*, s.action as signal_action, s.payload as signal_payload
                FROM trades t
                LEFT JOIN signals s ON s.id = t.signal_id
                {where}
                ORDER BY t.created_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        )

        trades = [dict(r) for r in rows]

    return {"trades": trades, "total": total, "limit": limit, "offset": offset}


# ═══════════════════════════════════════════════════════════════
# QUERY — PERFORMANCE STATS
# ═══════════════════════════════════════════════════════════════

async def get_stats(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Tinh metrics hieu suat: Win Rate, Profit Factor, Drawdown."""
    conditions = ["t.status = 'FILLED'"]
    params: list = []

    if symbol:
        conditions.append("t.symbol = ?")
        params.append(symbol.upper())

    where = f"WHERE {' AND '.join(conditions)}"

    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        rows = await db.execute_fetchall(
            f"SELECT pnl FROM trades t {where} AND pnl IS NOT NULL", params
        )

        pnl_list = [r[0] for r in rows]

        if not pnl_list:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_drawdown": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
            }

        wins = [p for p in pnl_list if p > 0]
        losses = [p for p in pnl_list if p <= 0]

        total_win = sum(wins) if wins else 0.0
        total_loss = abs(sum(losses)) if losses else 0.0

        # Max Drawdown (peak-to-trough)
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnl_list:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        return {
            "total_trades": len(pnl_list),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(pnl_list) * 100, 1) if pnl_list else 0.0,
            "total_pnl": round(sum(pnl_list), 2),
            "profit_factor": round(total_win / total_loss, 2) if total_loss > 0 else float("inf"),
            "avg_win": round(total_win / len(wins), 2) if wins else 0.0,
            "avg_loss": round(-total_loss / len(losses), 2) if losses else 0.0,
            "max_drawdown": round(-max_dd, 2),
            "best_trade": round(max(pnl_list), 2),
            "worst_trade": round(min(pnl_list), 2),
        }

# ═══════════════════════════════════════════════════════════════
# QUERY — EQUITY CURVE
# ═══════════════════════════════════════════════════════════════

async def get_equity_curve(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Tra ve equity curve data cho Chart.js."""
    conditions = ["t.status = 'FILLED'", "t.pnl IS NOT NULL"]
    params: list = []

    if symbol:
        conditions.append("t.symbol = ?")
        params.append(symbol.upper())

    where = f"WHERE {' AND '.join(conditions)}"

    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        rows = await db.execute_fetchall(
            f"""SELECT t.created_at, t.pnl, t.symbol, t.side
                FROM trades t {where}
                ORDER BY t.created_at ASC""",
            params,
        )

        labels = []
        cumulative_pnl = []
        trades_detail = []
        running = 0.0

        for r in rows:
            running += r[1]  # pnl
            labels.append(r[0])  # created_at
            cumulative_pnl.append(round(running, 2))
            trades_detail.append({
                "date": r[0],
                "pnl": r[1],
                "symbol": r[2],
                "side": r[3],
                "cumulative": round(running, 2),
            })

        return {
            "labels": labels,
            "cumulative_pnl": cumulative_pnl,
            "trades": trades_detail,
        }


# ═══════════════════════════════════════════════════════════════
# BRIEF CRUD
# ═══════════════════════════════════════════════════════════════

async def insert_brief(
    symbols_scanned: int,
    scan_data: Optional[str] = None,
    ai_analysis: Optional[str] = None,
    vision_data: Optional[str] = None,
    screenshot: Optional[str] = None,
    brief_text: Optional[str] = None,
    success: int = 1,
) -> int:
    """Lưu morning brief vào database."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO briefs
               (symbols_scanned, scan_data, ai_analysis, vision_data,
                screenshot, brief_text, success)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (symbols_scanned, scan_data, ai_analysis, vision_data,
             screenshot, brief_text, success),
        )
        await db.commit()
        brief_id = cursor.lastrowid
        log.info(f"Brief #{brief_id} saved ({symbols_scanned} symbols scanned)")
        return brief_id


async def get_briefs(
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """Truy vấn lịch sử morning briefs với pagination."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        row = await db.execute_fetchall(
            "SELECT COUNT(*) as cnt FROM briefs"
        )
        total = row[0][0] if row else 0

        limit = min(limit, 100)
        rows = await db.execute_fetchall(
            """SELECT * FROM briefs
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            [limit, offset],
        )

        briefs = []
        for r in rows:
            d = dict(r)
            # Parse JSON fields
            if d.get("scan_data"):
                try:
                    d["scan_data"] = json.loads(d["scan_data"])
                except Exception:
                    pass
            if d.get("vision_data"):
                try:
                    d["vision_data"] = json.loads(d["vision_data"])
                except Exception:
                    pass
            briefs.append(d)

    return {"briefs": briefs, "total": total, "limit": limit, "offset": offset}


async def get_brief_by_id(brief_id: int) -> Optional[Dict[str, Any]]:
    """Lấy chi tiết một brief theo ID."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM briefs WHERE id = ?", [brief_id]
        )
        if not rows:
            return None
        d = dict(rows[0])
        if d.get("scan_data"):
            try:
                d["scan_data"] = json.loads(d["scan_data"])
            except Exception:
                pass
        if d.get("vision_data"):
            try:
                d["vision_data"] = json.loads(d["vision_data"])
            except Exception:
                pass
        return d


async def get_db_counts() -> Dict[str, int]:
    """Đếm tổng records trong mỗi bảng cho system status."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        counts = {}
        for table in ("signals", "trades", "briefs"):
            rows = await db.execute_fetchall(f"SELECT COUNT(*) FROM {table}")
            counts[f"{table}_count"] = rows[0][0] if rows else 0
        return counts

