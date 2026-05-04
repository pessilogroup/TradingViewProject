"""
Binance Client — Sprint 7.2
Async MARKET + OCO order execution with position sizing and dry-run mode.
Supports both BUY entry → OCO SELL exit AND SELL entry → OCO BUY exit.
"""

import hashlib
import hmac
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

import aiohttp

import config

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════

@dataclass
class RiskParams:
    """Computed SL/TP levels and position sizing."""
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_pct: float
    take_profit_pct: float
    risk_reward_ratio: float
    quantity: float           # base asset qty
    cost: float               # quote asset cost
    risk_amount: float        # $ at risk
    account_balance: float
    position_pct: float       # % of account

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_price": round(self.entry_price, 8),
            "stop_loss_price": round(self.stop_loss_price, 8),
            "take_profit_price": round(self.take_profit_price, 8),
            "stop_loss_pct": round(self.stop_loss_pct * 100, 2),
            "take_profit_pct": round(self.take_profit_pct * 100, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "quantity": round(self.quantity, 8),
            "cost": round(self.cost, 2),
            "risk_amount": round(self.risk_amount, 2),
            "account_balance": round(self.account_balance, 2),
            "position_pct": round(self.position_pct * 100, 2),
        }


@dataclass
class OrderResult:
    """Unified result for smart order execution."""
    success: bool
    dry_run: bool
    side: str
    symbol: str
    entry_order: Dict[str, Any] = field(default_factory=dict)
    oco_order: Optional[Dict[str, Any]] = None
    risk: Optional[RiskParams] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "success": self.success,
            "dry_run": self.dry_run,
            "side": self.side,
            "symbol": self.symbol,
            "entry_order": self.entry_order,
            "oco_order": self.oco_order,
            "risk": self.risk.to_dict() if self.risk else None,
            "error": self.error,
        }
        return d


# ═══════════════════════════════════════════════════════════════
# BINANCE CLIENT
# ═══════════════════════════════════════════════════════════════

class BinanceClient:
    """Async Binance client — MARKET + OCO orders with risk management."""

    TESTNET_URL = "https://testnet.binance.vision"
    MAINNET_URL = "https://api.binance.com"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
        dry_run: bool = True,
    ):
        self.api_key = api_key or config.BINANCE_API_KEY
        self.api_secret = api_secret or config.BINANCE_API_SECRET
        self.testnet = testnet
        self.dry_run = dry_run
        self.base_url = self.TESTNET_URL if testnet else self.MAINNET_URL

        mode = []
        if dry_run:
            mode.append("DRY-RUN")
        mode.append("TESTNET" if testnet else "MAINNET")
        log.info(f"BinanceClient initialized [{', '.join(mode)}] → {self.base_url}")

    # ═══ SIGNING ═══════════════════════════════════════════════

    def _sign_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add timestamp + HMAC-SHA256 signature to params."""
        params["timestamp"] = int(time.time() * 1000)
        query = "&".join(f"{k}={v}" for k, v in params.items())
        sig = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = sig
        return params

    # ═══ HTTP ══════════════════════════════════════════════════

    async def _request(
        self, method: str, endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send signed request to Binance API."""
        signed = self._sign_params(params)
        headers = {"X-MBX-APIKEY": self.api_key}
        url = f"{self.base_url}{endpoint}"

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, params=signed, headers=headers) as resp:
                    data = await resp.json()
            else:
                async with session.post(url, params=signed, headers=headers) as resp:
                    data = await resp.json()

            if isinstance(data, dict) and data.get("code"):
                raise Exception(f"Binance API Error [{data.get('code')}]: {data.get('msg', data)}")

            return data

    # ═══ ACCOUNT ═══════════════════════════════════════════════

    async def get_account_balance(self, asset: str = "USDT") -> float:
        """Get free balance for a specific asset."""
        if self.dry_run:
            log.info(f"[DRY-RUN] get_account_balance({asset}) → $10,000.00")
            return 10000.0

        data = await self._request("GET", "/api/v3/account", {})
        for b in data.get("balances", []):
            if b["asset"] == asset.upper():
                return float(b["free"])
        return 0.0

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Get exchange info for symbol (LOT_SIZE, PRICE_FILTER, etc.)."""
        if self.dry_run:
            return {
                "symbol": symbol,
                "status": "TRADING",
                "baseAssetPrecision": 8,
                "quoteAssetPrecision": 8,
                "filters": [],
            }

        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/api/v3/exchangeInfo"
            async with session.get(url, params={"symbol": symbol}) as resp:
                data = await resp.json()
                symbols = data.get("symbols", [])
                if symbols:
                    return symbols[0]
                raise Exception(f"Symbol {symbol} not found on Binance")

    # ═══ POSITION SIZING ═══════════════════════════════════════

    @staticmethod
    def calculate_sl_tp(
        entry_price: float,
        side: str,
        sl_pct: float = None,
        tp_pct: float = None,
    ) -> Dict[str, float]:
        """Calculate Stop-Loss and Take-Profit prices.

        BUY side:  SL = entry × (1 - sl_pct), TP = entry × (1 + tp_pct)
        SELL side: SL = entry × (1 + sl_pct), TP = entry × (1 - tp_pct)
        """
        sl_pct = sl_pct if sl_pct is not None else config.STOP_LOSS_PCT
        tp_pct = tp_pct if tp_pct is not None else config.TAKE_PROFIT_PCT

        if side.upper() == "BUY":
            sl = entry_price * (1 - sl_pct)
            tp = entry_price * (1 + tp_pct)
        else:  # SELL
            sl = entry_price * (1 + sl_pct)
            tp = entry_price * (1 - tp_pct)

        rr = tp_pct / sl_pct if sl_pct > 0 else 0

        return {
            "stop_loss": round(sl, 8),
            "take_profit": round(tp, 8),
            "risk_reward": round(rr, 2),
        }

    @staticmethod
    def calculate_position_size(
        balance: float,
        entry_price: float,
        stop_price: float,
        risk_pct: float = None,
    ) -> float:
        """Calculate position size (base qty) based on risk %.

        Formula: qty = (balance × risk_pct) / |entry - stop|
        """
        risk_pct = risk_pct or config.RISK_PER_TRADE
        risk_amount = balance * risk_pct
        distance = abs(entry_price - stop_price)
        if distance == 0:
            return 0.0
        return risk_amount / distance

    # ═══ ORDERS ════════════════════════════════════════════════

    async def place_market_order(
        self, symbol: str, side: str, quote_qty: float = None, base_qty: float = None,
    ) -> Dict[str, Any]:
        """Place a MARKET order. Use quote_qty (USDT) OR base_qty (BTC)."""
        symbol_clean = symbol.replace("/", "").upper()
        side_upper = side.upper()

        params = {
            "symbol": symbol_clean,
            "side": side_upper,
            "type": "MARKET",
        }
        if quote_qty:
            params["quoteOrderQty"] = quote_qty
        elif base_qty:
            params["quantity"] = base_qty
        else:
            raise ValueError("Must provide either quote_qty or base_qty")

        if self.dry_run:
            fill_price = 67500.0  # Mock price
            qty = quote_qty / fill_price if quote_qty else base_qty
            mock = {
                "orderId": f"DRY-{uuid.uuid4().hex[:8].upper()}",
                "symbol": symbol_clean,
                "side": side_upper,
                "type": "MARKET",
                "status": "FILLED",
                "executedQty": str(round(qty, 8)),
                "cummulativeQuoteQty": str(round(qty * fill_price, 2)),
                "fills": [{"price": str(fill_price), "qty": str(round(qty, 8)), "commission": "0"}],
                "_dry_run": True,
            }
            log.info(f"[DRY-RUN] MARKET {side_upper} {symbol_clean} "
                      f"qty={round(qty, 8)} cost=${round(qty * fill_price, 2)}")
            return mock

        return await self._request("POST", "/api/v3/order", params)

    async def place_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        take_profit_price: float,
        stop_price: float,
        stop_limit_price: float,
    ) -> Dict[str, Any]:
        """Place an OCO order (one-cancels-other) for SL + TP exit."""
        symbol_clean = symbol.replace("/", "").upper()
        side_upper = side.upper()

        params = {
            "symbol": symbol_clean,
            "side": side_upper,
            "quantity": round(quantity, 8),
            "price": round(take_profit_price, 2),       # LIMIT (TP)
            "stopPrice": round(stop_price, 2),           # STOP trigger
            "stopLimitPrice": round(stop_limit_price, 2),# STOP_LIMIT fill
            "stopLimitTimeInForce": "GTC",
        }

        if self.dry_run:
            mock = {
                "orderListId": f"DRY-OCO-{uuid.uuid4().hex[:8].upper()}",
                "listStatusType": "EXEC_STARTED",
                "listOrderStatus": "EXECUTING",
                "symbol": symbol_clean,
                "orders": [
                    {"orderId": f"DRY-TP-{uuid.uuid4().hex[:6].upper()}", "type": "LIMIT_MAKER"},
                    {"orderId": f"DRY-SL-{uuid.uuid4().hex[:6].upper()}", "type": "STOP_LOSS_LIMIT"},
                ],
                "take_profit_price": take_profit_price,
                "stop_loss_price": stop_price,
                "_dry_run": True,
            }
            log.info(f"[DRY-RUN] OCO {side_upper} {symbol_clean} "
                      f"qty={round(quantity, 8)} TP=${take_profit_price} SL=${stop_price}")
            return mock

        return await self._request("POST", "/api/v3/order/oco", params)

    # ═══ SMART ORDER ═══════════════════════════════════════════

    async def execute_smart_order(
        self,
        symbol: str,
        side: str,
        entry_price: float = None,
        quote_qty: float = None,
        sl_pct: float = None,
        tp_pct: float = None,
        risk_pct: float = None,
        asset: str = "USDT",
    ) -> OrderResult:
        """Full workflow: MARKET entry → OCO exit with position sizing.

        Steps:
        1. Get account balance
        2. Calculate SL/TP levels
        3. Calculate position size (risk-based)
        4. Place MARKET order
        5. Place OCO exit order
        6. Return unified result
        """
        symbol_clean = symbol.replace("/", "").upper()
        side_upper = side.upper()
        sl_pct = sl_pct or config.STOP_LOSS_PCT
        tp_pct = tp_pct or config.TAKE_PROFIT_PCT
        risk_pct = risk_pct or config.RISK_PER_TRADE

        try:
            # 1. Account balance
            balance = await self.get_account_balance(asset)
            log.info(f"Account balance: ${balance:,.2f} {asset}")

            # 2. SL/TP levels
            levels = self.calculate_sl_tp(entry_price, side_upper, sl_pct, tp_pct)
            sl_price = levels["stop_loss"]
            tp_price = levels["take_profit"]
            rr_ratio = levels["risk_reward"]

            # 3. Position sizing
            qty = self.calculate_position_size(balance, entry_price, sl_price, risk_pct)
            cost = qty * entry_price
            risk_amount = balance * risk_pct

            # Cap at available balance (use max 95% to cover fees)
            max_cost = balance * 0.95
            if cost > max_cost:
                qty = max_cost / entry_price
                cost = qty * entry_price
                log.warning(f"Position capped to 95% of balance: ${cost:,.2f}")

            risk_params = RiskParams(
                entry_price=entry_price,
                stop_loss_price=sl_price,
                take_profit_price=tp_price,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                risk_reward_ratio=rr_ratio,
                quantity=qty,
                cost=cost,
                risk_amount=risk_amount,
                account_balance=balance,
                position_pct=cost / balance if balance > 0 else 0,
            )

            log.info(f"Smart Order: {side_upper} {symbol_clean} | "
                     f"Entry=${entry_price:,.2f} SL=${sl_price:,.2f} TP=${tp_price:,.2f} | "
                     f"Qty={qty:.8f} Cost=${cost:,.2f} R:R={rr_ratio}")

            # 4. MARKET entry
            if quote_qty:
                entry_result = await self.place_market_order(symbol_clean, side_upper, quote_qty=quote_qty)
            else:
                entry_result = await self.place_market_order(symbol_clean, side_upper, base_qty=qty)

            # Get actual fill price from entry
            exec_qty = float(entry_result.get("executedQty", qty))
            cum_quote = float(entry_result.get("cummulativeQuoteQty", cost))
            fill_price = cum_quote / exec_qty if exec_qty > 0 else entry_price

            # Recalculate SL/TP from actual fill price
            if abs(fill_price - entry_price) > 0.01:
                levels = self.calculate_sl_tp(fill_price, side_upper, sl_pct, tp_pct)
                sl_price = levels["stop_loss"]
                tp_price = levels["take_profit"]
                risk_params.entry_price = fill_price
                risk_params.stop_loss_price = sl_price
                risk_params.take_profit_price = tp_price

            # 5. OCO exit (opposite side)
            exit_side = "SELL" if side_upper == "BUY" else "BUY"
            # Stop limit price slightly worse than stop price (0.5% buffer)
            if exit_side == "SELL":
                stop_limit = sl_price * 0.995  # Sell slightly lower
            else:
                stop_limit = sl_price * 1.005  # Buy slightly higher

            oco_result = await self.place_oco_order(
                symbol=symbol_clean,
                side=exit_side,
                quantity=exec_qty,
                take_profit_price=tp_price,
                stop_price=sl_price,
                stop_limit_price=stop_limit,
            )

            log.info(f"Smart Order complete: entry={entry_result.get('orderId')} "
                     f"oco={oco_result.get('orderListId')}")

            return OrderResult(
                success=True,
                dry_run=self.dry_run,
                side=side_upper,
                symbol=symbol_clean,
                entry_order=entry_result,
                oco_order=oco_result,
                risk=risk_params,
            )

        except Exception as e:
            log.error(f"Smart Order FAILED: {e}")
            return OrderResult(
                success=False,
                dry_run=self.dry_run,
                side=side_upper,
                symbol=symbol_clean,
                error=str(e),
            )


# ═══════════════════════════════════════════════════════════════
# TELEGRAM FORMATTING
# ═══════════════════════════════════════════════════════════════

def format_order_telegram(result: OrderResult) -> str:
    """Format OrderResult for Telegram notification."""
    if not result.success:
        return (
            f"❌ **ORDER FAILED** — {result.symbol}\n"
            f"- Side: `{result.side}`\n"
            f"- Error: `{result.error}`\n"
            f"- Dry-Run: {'Yes' if result.dry_run else 'No'}"
        )

    tag = " [DRY-RUN]" if result.dry_run else ""
    r = result.risk

    # Entry info
    entry = result.entry_order
    order_id = entry.get("orderId", "N/A")
    exec_qty = entry.get("executedQty", "0")
    exec_cost = entry.get("cummulativeQuoteQty", "0")

    # OCO info
    oco_id = "N/A"
    if result.oco_order:
        oco_id = result.oco_order.get("orderListId", "N/A")

    msg = (
        f"✅ **SMART ORDER** — {result.symbol}{tag}\n\n"
        f"📊 **Entry: MARKET {result.side}**\n"
        f"- Fill Price: `${r.entry_price:,.2f}`\n"
        f"- Quantity: `{exec_qty}`\n"
        f"- Cost: `${float(exec_cost):,.2f}`\n"
        f"- Order ID: `{order_id}`\n\n"
        f"🛡️ **Risk Management:**\n"
        f"- Stop-Loss: `${r.stop_loss_price:,.2f}` ({r.stop_loss_pct * 100:.1f}%)\n"
        f"- Take-Profit: `${r.take_profit_price:,.2f}` (+{r.take_profit_pct * 100:.1f}%)\n"
        f"- R:R Ratio: `{r.risk_reward_ratio:.2f}`\n"
        f"- OCO ID: `{oco_id}`\n\n"
        f"💰 **Position Sizing:**\n"
        f"- Account: `${r.account_balance:,.2f}`\n"
        f"- Risk: `{r.stop_loss_pct * 100:.1f}%` ($`{r.risk_amount:,.2f}`)\n"
        f"- Position: `${r.cost:,.2f}` ({r.position_pct * 100:.1f}% account)"
    )
    return msg


# ═══════════════════════════════════════════════════════════════
# MODULE-LEVEL CLIENT (singleton)
# ═══════════════════════════════════════════════════════════════

_client: Optional[BinanceClient] = None


def get_client() -> BinanceClient:
    """Get or create singleton BinanceClient."""
    global _client
    if _client is None:
        _client = BinanceClient(
            api_key=config.BINANCE_API_KEY,
            api_secret=config.BINANCE_API_SECRET,
            testnet=config.BINANCE_TESTNET,
            dry_run=config.BINANCE_DRY_RUN,
        )
    return _client
