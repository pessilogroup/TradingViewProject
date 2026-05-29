"""
vps_analyzer.py — AI Analyzer Worker for SERVER C (Phase 5).

Daemon worker that runs on SERVER C in the 3-server pipeline:
  SERVER A (VBS) → SERVER C (Analyzer) → SERVER B (Executor)

Flow:
  1. Poll raw signals from SERVER A's VPS Buffer Service (VBS)
  2. Run RAG analysis (ChromaDB + AI) on each signal
  3. Compute position sizing based on risk management rules
  4. Forward approved trades to SERVER B's execution endpoint
  5. ACK processed signals back to SERVER A
"""

import asyncio
import logging
import aiohttp
import socket
from typing import Dict, Any, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import rag

log = logging.getLogger(__name__)


class VpsAnalyzerWorker:
    """AI Analyzer Worker for SERVER C.
    Polls raw signals from SERVER A (VBS), runs RAG analysis,
    computes position sizing, and forwards approved trades to SERVER B.
    """

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.consumer_id = "server-c-analyzer"
        self.poll_interval = config.VPS_POLL_INTERVAL_SECONDS

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or initialize the persistent aiohttp ClientSession."""
        if not self._session or self._session.closed:
            conn = aiohttp.TCPConnector(family=socket.AF_INET)
            self._session = aiohttp.ClientSession(connector=conn)
        return self._session

    async def close(self):
        """Close the ClientSession gracefully."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def poll_and_analyze(self) -> List[Dict[str, Any]]:
        """Poll raw signals from SERVER A's VBS, run RAG analysis on each.

        Returns:
            List of analyzed result dicts, each containing:
              - queue_id: int — VBS queue ID for ACK
              - approved: bool — whether the trade is approved
              - trade_payload: dict — payload to forward to Server B (if approved)
              - reason: str — rejection reason (if not approved)
        """
        url = f"{config.VPS_BUFFER_URL}/consume"
        params = {
            "consumer_id": self.consumer_id,
            "limit": 5,
        }
        headers = {
            "X-Buffer-Secret": config.VPS_BUFFER_SECRET,
        }

        results: List[Dict[str, Any]] = []

        try:
            session = await self.get_session()
            async with session.get(url, params=params, headers=headers, timeout=15) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error(
                        f"[VpsAnalyzer] Failed to poll VBS (HTTP {resp.status}): {body[:200]}"
                    )
                    return results
                data = await resp.json()
        except Exception as e:
            log.warning(f"[VpsAnalyzer] Connection error polling VBS: {e}")
            return results

        signals = data.get("signals", [])
        if not signals:
            return results

        log.info(f"[VpsAnalyzer] Received {len(signals)} signal(s) from VBS")

        for signal in signals:
            queue_id = signal.get("queue_id")
            try:
                analyzed = await self._analyze_signal(signal)
                if analyzed is not None:
                    results.append({
                        "queue_id": queue_id,
                        "approved": True,
                        "trade_payload": analyzed,
                    })
                else:
                    results.append({
                        "queue_id": queue_id,
                        "approved": False,
                        "reason": "RAG analysis rejected signal — does not meet Minervini criteria",
                    })
            except Exception as e:
                log.exception(f"[VpsAnalyzer] Error analyzing signal #{queue_id}: {e}")
                results.append({
                    "queue_id": queue_id,
                    "approved": False,
                    "reason": f"Analysis error: {str(e)[:200]}",
                })

        return results

    async def _analyze_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run RAG analysis on a single signal, compute position sizing.

        Steps:
          1. Build RAG query from signal
          2. Query ChromaDB via rag.query_knowledge()
          3. Generate trading advice via rag.generate_trading_advice()
          4. Parse AI response to determine approval
          5. Compute position sizing based on RISK_PER_TRADE, STOP_LOSS_PCT
          6. Return trade payload if approved, None if rejected

        Args:
            signal: Raw signal dict from VBS with keys:
                queue_id, symbol, action, price, payload, etc.

        Returns:
            Trade payload dict if approved, None if rejected.
        """
        symbol = signal.get("symbol", "")
        action = signal.get("action", "")
        price = signal.get("price")
        payload = signal.get("payload", {})
        queue_id = signal.get("queue_id")

        log.info(f"[VpsAnalyzer] Analyzing signal #{queue_id}: {symbol} {action} @ {price}")

        # 1. Build RAG query from signal context
        rag_query = rag.build_rag_query(symbol, action, payload)

        # 2. Query ChromaDB for relevant Minervini knowledge
        rag_chunks = rag.query_knowledge(rag_query, n_results=config.RAG_TOP_K)

        # 3. Generate trading advice via AI (Claude/Gemini)
        price_str = str(price) if price is not None else "N/A"
        advice = await rag.generate_trading_advice(
            symbol=symbol,
            action=action,
            price=price_str,
            payload=payload,
            rag_chunks=rag_chunks,
        )

        log.info(f"[VpsAnalyzer] AI advice for #{queue_id}: {advice[:100]}...")

        # 4. Parse advice to determine approval
        #    Check for explicit rejection/warning keywords in the AI response
        advice_lower = advice.lower()
        rejected_keywords = ["⚠️", "chờ thêm", "không nên", "rejected", "wait", "avoid"]
        approved_keywords = ["mua", "buy", "bán", "sell", "mạnh", "strong", "approved"]

        is_rejected = any(kw in advice_lower for kw in rejected_keywords)
        is_approved = any(kw in advice_lower for kw in approved_keywords)

        # If advice contains error messages (RAG unavailable), reject
        if advice.startswith("⚠️"):
            log.warning(f"[VpsAnalyzer] Signal #{queue_id} rejected: RAG error - {advice[:100]}")
            return None

        # Default: approve if not explicitly rejected, or if approved keywords found
        if is_rejected and not is_approved:
            log.info(f"[VpsAnalyzer] Signal #{queue_id} rejected by AI analysis")
            return None

        # 5. Compute position sizing
        try:
            price_val = float(price) if price is not None else 0.0
        except (ValueError, TypeError):
            price_val = 0.0

        if price_val <= 0:
            log.warning(f"[VpsAnalyzer] Signal #{queue_id}: invalid price {price}, rejecting")
            return None

        # Position sizing: risk_amount = account_equity * RISK_PER_TRADE
        # qty = risk_amount / (price * STOP_LOSS_PCT)
        # Use MAX_QUOTE_QTY as the cap for max position
        risk_per_trade = config.RISK_PER_TRADE   # e.g., 0.02 (2%)
        stop_loss_pct = config.STOP_LOSS_PCT     # e.g., 0.08 (8%)
        max_quote_qty = config.MAX_QUOTE_QTY     # e.g., 1000 USDT

        # Risk amount based on max_quote_qty as proxy for account equity
        risk_amount = max_quote_qty * risk_per_trade
        # Dollar risk per unit = price * stop_loss_pct
        dollar_risk_per_unit = price_val * stop_loss_pct

        if dollar_risk_per_unit > 0:
            qty = risk_amount / dollar_risk_per_unit
        else:
            qty = 0.0

        # Cap the total quote value to MAX_QUOTE_QTY
        quote_value = qty * price_val
        if quote_value > max_quote_qty:
            qty = max_quote_qty / price_val

        # Compute SL and TP prices
        if action.lower() in ("buy", "long"):
            sl_price = round(price_val * (1 - stop_loss_pct), 8)
            tp_price = round(price_val * (1 + config.TAKE_PROFIT_PCT), 8)
        else:
            sl_price = round(price_val * (1 + stop_loss_pct), 8)
            tp_price = round(price_val * (1 - config.TAKE_PROFIT_PCT), 8)

        # 6. Build trade payload for Server B
        trade_payload = {
            "symbol": symbol,
            "action": action,
            "price": price_val,
            "qty": round(qty, 8),
            "sl": sl_price,
            "tp": tp_price,
            "analysis": advice,
            "risk_per_trade": risk_per_trade,
            "stop_loss_pct": stop_loss_pct,
            "exchange": payload.get("exchange", config.DEFAULT_EXCHANGE),
        }

        log.info(
            f"[VpsAnalyzer] Signal #{queue_id} APPROVED: "
            f"{symbol} {action} qty={trade_payload['qty']} "
            f"sl={sl_price} tp={tp_price}"
        )

        return trade_payload

    async def forward_to_server_b(self, trade_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Forward approved trade to the execution endpoint, prioritizing Local Windows.
        Falls back to SERVER B (Cloud Backup) if Local is offline or fails to execute.

        Args:
            trade_payload: Dict with symbol, action, price, qty, sl, tp, analysis, etc.

        Returns:
            Response dict from the executing server, or error dict on failure.
        """
        # Try Local Windows execution first if configured
        if config.LOCAL_EXECUTE_URL:
            local_url = f"{config.LOCAL_EXECUTE_URL}/api/execute-trade"
            local_headers = {
                "X-Server-B-Secret": config.LOCAL_EXECUTE_SECRET,
                "Content-Type": "application/json",
            }
            log.info(f"[VpsAnalyzer] Attempting execution on Local Windows: {local_url}")
            try:
                session = await self.get_session()
                # Use a lower connection & total timeout for Local to trigger failover quickly
                timeout = aiohttp.ClientTimeout(connect=5, total=10)
                async with session.post(
                    local_url, json=trade_payload, headers=local_headers, timeout=timeout
                ) as resp:
                    body = await resp.json()
                    if resp.status == 200:
                        log.info(
                            f"[VpsAnalyzer] Local Windows executed trade: "
                            f"{trade_payload['symbol']} {trade_payload['action']}"
                        )
                        return {"success": True, "status": resp.status, "data": body, "executed_on": "local"}
                    else:
                        log.warning(
                            f"[VpsAnalyzer] Local Windows rejected trade (HTTP {resp.status}): {body}. "
                            f"Falling back to Server B."
                        )
            except Exception as e:
                log.warning(f"[VpsAnalyzer] Local Windows offline or execution failed: {e}. Falling back to Server B.")
                # Send a Telegram alert indicating local is offline and falling back
                try:
                    from notifier import send_telegram_alert
                    await send_telegram_alert(
                        f"⚠️ **Local Windows Offline / Gặp sự cố**\n"
                        f"- Lỗi: `{str(e)[:150]}`\n"
                        f"- Trạng thái: Tự động chuyển luồng giao dịch sang **Server B (Cloud Backup)**..."
                    )
                except Exception as t_err:
                    log.warning(f"Failed to send Telegram alert for failover: {t_err}")

        # Fallback to Server B
        url = f"{config.SERVER_B_EXECUTE_URL}/api/execute-trade"
        headers = {
            "X-Server-B-Secret": config.SERVER_B_SECRET,
            "Content-Type": "application/json",
        }
        log.info(f"[VpsAnalyzer] Forwarding trade to Server B (Cloud Backup): {url}")

        try:
            session = await self.get_session()
            async with session.post(
                url, json=trade_payload, headers=headers, timeout=30
            ) as resp:
                body = await resp.json()
                if resp.status == 200:
                    log.info(
                        f"[VpsAnalyzer] Server B accepted trade: "
                        f"{trade_payload['symbol']} {trade_payload['action']}"
                    )
                    return {"success": True, "status": resp.status, "data": body, "executed_on": "server_b"}
                else:
                    log.error(
                        f"[VpsAnalyzer] Server B rejected trade (HTTP {resp.status}): "
                        f"{body}"
                    )
                    return {
                        "success": False,
                        "status": resp.status,
                        "error": body.get("detail", str(body)),
                    }
        except aiohttp.ContentTypeError:
            log.error("[VpsAnalyzer] Server B returned non-JSON response")
            return {"success": False, "status": 500, "error": "Non-JSON response from Server B"}
        except Exception as e:
            log.error(f"[VpsAnalyzer] Error forwarding to Server B: {e}")
            return {"success": False, "status": 0, "error": str(e)}

    async def _ack_signal(self, queue_id: int, status: str, error_msg: str = "") -> bool:
        """ACK processed signal back to SERVER A's VBS.

        Args:
            queue_id: VBS queue ID to acknowledge.
            status: One of 'executed', 'failed', 'rejected'.
            error_msg: Optional error/rejection description.

        Returns:
            True if ACK succeeded, False otherwise.
        """
        url = f"{config.VPS_BUFFER_URL}/ack"
        headers = {
            "X-Buffer-Secret": config.VPS_BUFFER_SECRET,
            "Content-Type": "application/json",
        }
        payload = {
            "acks": [{
                "queue_id": queue_id,
                "status": status,
                "error_msg": error_msg,
            }]
        }

        try:
            session = await self.get_session()
            async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    log.info(f"[VpsAnalyzer] ACK sent for #{queue_id} (status={status})")
                    return True
                else:
                    body = await resp.text()
                    log.error(
                        f"[VpsAnalyzer] Failed to ACK #{queue_id} "
                        f"(HTTP {resp.status}): {body[:200]}"
                    )
                    return False
        except Exception as e:
            log.error(f"[VpsAnalyzer] Connection error sending ACK for #{queue_id}: {e}")
            return False

    async def run(self):
        """Main daemon loop: poll → analyze → forward → ack.

        Runs continuously until cancelled. For each poll cycle:
          1. Polls raw signals from VBS
          2. Runs RAG analysis on each signal
          3. Forwards approved trades to Server B
          4. ACKs all processed signals back to VBS
        """
        log.info(
            f"[VpsAnalyzer] Starting analyzer worker "
            f"(consumer_id={self.consumer_id}, poll_interval={self.poll_interval}s)"
        )
        while True:
            try:
                signals = await self.poll_and_analyze()
                for analyzed in signals:
                    queue_id = analyzed["queue_id"]
                    if analyzed.get("approved"):
                        result = await self.forward_to_server_b(analyzed["trade_payload"])
                        if result.get("success"):
                            await self._ack_signal(queue_id, "executed")
                        else:
                            await self._ack_signal(
                                queue_id, "failed",
                                result.get("error", "Server B execution failed")
                            )
                    else:
                        await self._ack_signal(
                            queue_id, "rejected",
                            analyzed.get("reason", "")
                        )
            except asyncio.CancelledError:
                log.info("[VpsAnalyzer] Daemon loop cancelled. Shutting down.")
                break
            except Exception as e:
                log.exception(f"[VpsAnalyzer] Error in run loop: {e}")
            await asyncio.sleep(self.poll_interval)

        await self.close()


if __name__ == "__main__":
    import asyncio
    worker = VpsAnalyzerWorker()
    asyncio.run(worker.run())
