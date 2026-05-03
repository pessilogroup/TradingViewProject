"""
P6 — Analysis Engine
Trend Template scorer (8 Minervini criteria) + VCP detector.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TrendTemplateResult:
    score: int                          # 0-8
    criteria: dict[str, bool]           # {criterion_name: passed}
    stage: str                          # "Stage 2", "Stage 1", "Stage 3/4", "Unknown"
    summary: str                        # Human-readable summary


@dataclass
class VCPResult:
    detected: bool
    volume_ratio: float                 # current vol / 20-period avg (< 0.5 = contraction)
    range_ratio: float                  # (H-L) / ATR14 (< 0.5 = narrow)
    pivot_level: Optional[float]        # estimated breakout pivot
    note: str


@dataclass
class ScanResult:
    symbol: str
    price: float
    change_pct: float
    trend_template: TrendTemplateResult
    vcp: VCPResult
    volume: float
    volume_avg: Optional[float]
    error: Optional[str] = None


def score_trend_template(
    price: float,
    sma50: Optional[float],
    sma150: Optional[float],
    sma200: Optional[float],
    high_52w: Optional[float],
    low_52w: Optional[float],
    sma200_slope: Optional[float] = None,   # positive = trending up
    rs_ratio: Optional[float] = None,       # > 1.0 = outperforming benchmark
) -> TrendTemplateResult:
    """
    Score 8 Minervini Trend Template criteria.

    Criteria:
    1. Price > SMA150 AND Price > SMA200
    2. SMA150 > SMA200
    3. SMA200 trending up (slope > 0, need at least 1 month = 20 bars)
    4. SMA50 > SMA150 AND SMA50 > SMA200
    5. Price > SMA50
    6. Price >= 52-week low × 1.30 (at least 30% above 52w low)
    7. Price >= 52-week high × 0.75 (within 25% of 52w high)
    8. Relative Strength vs benchmark > 1.0 (outperforming)
    """
    criteria = {}

    # 1. Price > SMA150 & SMA200
    if sma150 is not None and sma200 is not None:
        criteria["price_above_ma150_200"] = price > sma150 and price > sma200
    else:
        criteria["price_above_ma150_200"] = None

    # 2. SMA150 > SMA200
    if sma150 is not None and sma200 is not None:
        criteria["ma150_above_ma200"] = sma150 > sma200
    else:
        criteria["ma150_above_ma200"] = None

    # 3. SMA200 trending up
    if sma200_slope is not None:
        criteria["ma200_trending_up"] = sma200_slope > 0
    else:
        criteria["ma200_trending_up"] = None  # unknown

    # 4. SMA50 > SMA150 & SMA200
    if sma50 is not None and sma150 is not None and sma200 is not None:
        criteria["ma50_above_ma150_200"] = sma50 > sma150 and sma50 > sma200
    else:
        criteria["ma50_above_ma150_200"] = None

    # 5. Price > SMA50
    if sma50 is not None:
        criteria["price_above_ma50"] = price > sma50
    else:
        criteria["price_above_ma50"] = None

    # 6. Price >= 52w low × 1.30
    if low_52w is not None and low_52w > 0:
        criteria["above_52w_low_130pct"] = price >= low_52w * 1.30
    else:
        criteria["above_52w_low_130pct"] = None

    # 7. Price >= 52w high × 0.75 (within 25% of high)
    if high_52w is not None and high_52w > 0:
        criteria["within_25pct_of_52w_high"] = price >= high_52w * 0.75
    else:
        criteria["within_25pct_of_52w_high"] = None

    # 8. RS vs benchmark
    if rs_ratio is not None:
        criteria["rs_outperforming"] = rs_ratio > 1.0
    else:
        criteria["rs_outperforming"] = None

    # Score: count True (None = unknown, treated as 0)
    score = sum(1 for v in criteria.values() if v is True)

    # Stage classification
    if score >= 7:
        stage = "Stage 2 ⭐"
    elif score >= 5:
        stage = "Stage 1/2 Transition"
    elif score >= 3:
        stage = "Stage 1 (Base)"
    else:
        stage = "Stage 3/4 (Avoid)"

    # Summary
    passed = [k for k, v in criteria.items() if v is True]
    failed = [k for k, v in criteria.items() if v is False]
    summary = f"Score {score}/8 — {stage}. ✅ {len(passed)} passed, ❌ {len(failed)} failed"

    return TrendTemplateResult(score=score, criteria=criteria, stage=stage, summary=summary)


def detect_vcp(
    price: float,
    high: float,
    low: float,
    volume: float,
    volume_avg20: Optional[float],
    atr14: Optional[float],
    high_52w: Optional[float],
) -> VCPResult:
    """
    Detect VCP (Volatility Contraction Pattern).

    Signals:
    - Volume < 50% of 20-period average (drying up = smart money accumulating)
    - Price range (H-L) < 50% of ATR14 (contraction)
    - Price within 10% of 52w high (near breakout zone)
    """
    volume_ratio = (volume / volume_avg20) if volume_avg20 and volume_avg20 > 0 else 1.0
    current_range = high - low
    range_ratio = (current_range / atr14) if atr14 and atr14 > 0 else 1.0

    vol_contracting = volume_ratio < 0.5
    range_contracting = range_ratio < 0.5
    near_high = (price >= high_52w * 0.90) if high_52w and high_52w > 0 else False

    detected = vol_contracting and range_contracting

    # Pivot estimate: slight above recent high
    pivot_level = round(high * 1.005, 2) if detected else None

    if detected and near_high:
        note = f"VCP xác nhận: vol={volume_ratio:.0%} avg, range={range_ratio:.0%} ATR — gần 52w high ⭐ WATCH"
    elif detected:
        note = f"VCP contraction: vol={volume_ratio:.0%} avg, range={range_ratio:.0%} ATR"
    elif vol_contracting:
        note = f"Volume co lại ({volume_ratio:.0%} avg) nhưng range chưa hẹp"
    elif range_contracting:
        note = f"Range hẹp ({range_ratio:.0%} ATR) nhưng volume chưa co"
    else:
        note = f"Không có VCP: vol={volume_ratio:.0%} avg, range={range_ratio:.0%} ATR"

    return VCPResult(
        detected=detected,
        volume_ratio=volume_ratio,
        range_ratio=range_ratio,
        pivot_level=pivot_level,
        note=note,
    )


async def scan_symbols(symbols: list[str], mcp_client) -> list[ScanResult]:
    """
    Batch scan symbols: fetch data from MCP, score TT + VCP.
    Returns sorted by TT score descending.
    """
    from mcp_client import QuoteData, StudyValues

    raw_data = await mcp_client.batch_run(symbols)
    results = []

    for item in raw_data:
        sym = item["symbol"]

        if item.get("error"):
            results.append(ScanResult(
                symbol=sym, price=0, change_pct=0,
                trend_template=TrendTemplateResult(0, {}, "Unknown", "MCP error"),
                vcp=VCPResult(False, 1.0, 1.0, None, "Data unavailable"),
                volume=0, volume_avg=None,
                error=item["error"]
            ))
            continue

        quote: QuoteData = item["quote"]
        studies: StudyValues = item["studies"]
        ohlcv = item.get("ohlcv_summary", {})

        tt = score_trend_template(
            price=quote.close,
            sma50=studies.sma50,
            sma150=studies.sma150,
            sma200=studies.sma200,
            high_52w=studies.high_52w,
            low_52w=studies.low_52w,
            rs_ratio=studies.rs_line,
        )

        vcp = detect_vcp(
            price=quote.close,
            high=quote.high,
            low=quote.low,
            volume=quote.volume,
            volume_avg20=studies.volume_avg20,
            atr14=studies.atr14,
            high_52w=studies.high_52w,
        )

        results.append(ScanResult(
            symbol=sym,
            price=quote.close,
            change_pct=quote.change_pct,
            trend_template=tt,
            vcp=vcp,
            volume=quote.volume,
            volume_avg=studies.volume_avg20,
            error=None,
        ))

    # Sort: VCP detected first, then by TT score desc
    results.sort(key=lambda r: (r.vcp.detected, r.trend_template.score), reverse=True)
    return results
