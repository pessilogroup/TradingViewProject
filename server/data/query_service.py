import aiosqlite
import json
import logging
from typing import Optional, Dict, Any

import config

log = logging.getLogger(__name__)

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
# QUERY — BRIEFS
# ═══════════════════════════════════════════════════════════════

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
