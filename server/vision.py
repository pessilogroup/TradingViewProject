"""
P7 Sprint 7.5 — AI Vision Analysis
Gửi chart screenshot cho Claude Vision để nhận diện pattern trực quan.

Capabilities:
    - VCP (Volatility Contraction Pattern) visual detection
    - Cup-with-Handle, Ascending Base, Flat Base identification
    - Volume analysis from chart visual
    - Support/Resistance zone detection
    - Combined score: algorithmic (TT/VCP) + visual (Claude Vision)
"""

import logging
import base64
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Lazy import
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

import config


# ── Vision Analysis Prompt ────────────────────────────────────────────────

VISION_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích kỹ thuật theo phương pháp SEPA của Mark Minervini.
Bạn đang nhìn vào biểu đồ TradingView của một cổ phiếu/crypto.

Nhiệm vụ: Phân tích biểu đồ này dựa trên Minervini methodology và trả về kết quả có cấu trúc."""

VISION_USER_PROMPT = """Phân tích biểu đồ TradingView này cho {symbol}:

## DỮ LIỆU ĐỊNH LƯỢNG (từ scanner)
{algo_context}

## YÊU CẦU PHÂN TÍCH BIỂU ĐỒ
Nhìn vào biểu đồ và đánh giá:

1. **Pattern Recognition** — Bạn nhận dạng pattern gì?
   - VCP (Volatility Contraction Pattern): có thấy đáy nâng dần + volume giảm?
   - Cup-with-Handle / Ascending Base / Flat Base / High Tight Flag?
   - Khu vực tích lũy (accumulation)?

2. **Trend Assessment** — Xu hướng hiện tại:
   - Stage nào? (Stage 1 base / Stage 2 uptrend / Stage 3 top / Stage 4 decline)
   - Moving Averages có xếp đúng thứ tự (50 > 150 > 200)?
   - Price action có hẹp lại (contraction) không?

3. **Volume Analysis** — Phân tích volume trên chart:
   - Volume có giảm dần trong base? (dấu hiệu tích cực)
   - Có volume spike gần đây? (breakout signal)
   - Dry-up volume? (institutional accumulation)

4. **Key Levels**:
   - Pivot point / breakout level ước tính
   - Support level gần nhất
   - Resistance level gần nhất

5. **Visual Confidence Score**:
   - 1-10: Mức độ tin cậy của setup dựa trên biểu đồ
   - Lý do ngắn gọn

## FORMAT TRẢ LỜI
Trả lời NGẮN GỌN (dưới 250 từ), dùng emoji, format Telegram-friendly.
Bắt đầu bằng: 👁️ VISUAL ANALYSIS — {symbol}"""


def _encode_image(image_path: Path) -> Optional[str]:
    """Encode image to base64 for Claude Vision API."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        log.error(f"Failed to encode image {image_path}: {e}")
        return None


def _get_media_type(image_path: Path) -> str:
    """Detect media type from file extension."""
    ext = image_path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/png")


def _build_algo_context(scan_result: dict = None) -> str:
    """Build algorithmic context string from scan result."""
    if not scan_result:
        return "Không có dữ liệu scanner."

    lines = []
    if "price" in scan_result:
        lines.append(f"- Price: {scan_result['price']:,.2f}")
    if "trend_template_score" in scan_result:
        lines.append(f"- Trend Template: {scan_result['trend_template_score']}/8")
    if "trend_template_stage" in scan_result:
        lines.append(f"- Stage: {scan_result['trend_template_stage']}")
    if "vcp_detected" in scan_result:
        vcp = "✅ Detected" if scan_result["vcp_detected"] else "❌ Not detected"
        lines.append(f"- VCP (algorithmic): {vcp}")
    if "volume_ratio" in scan_result and scan_result["volume_ratio"]:
        lines.append(f"- Volume ratio: {scan_result['volume_ratio']*100:.0f}% of avg")
    if "pivot_level" in scan_result and scan_result["pivot_level"]:
        lines.append(f"- Pivot estimate: {scan_result['pivot_level']:,.2f}")

    return "\n".join(lines) if lines else "Không có dữ liệu scanner."


async def analyze_chart_vision(
    image_path: Path,
    symbol: str,
    scan_result: dict = None,
    model: str = "claude-sonnet-4-5",
) -> dict:
    """
    Gửi chart screenshot cho Claude Vision để phân tích pattern.

    Args:
        image_path: Path tới screenshot PNG
        symbol: Mã symbol (VD: "BTCUSDT")
        scan_result: Dict scan result từ analysis.py (optional — for combined scoring)
        model: Claude model (default: claude-sonnet-4-5 — supports vision)

    Returns:
        dict {
            "symbol": str,
            "analysis": str,      # Claude's visual analysis text
            "confidence": int,    # 1-10 visual confidence (parsed)
            "patterns": list,     # Detected patterns
            "combined_score": str, # Algo + Visual combined
            "error": str or None,
        }
    """
    result = {
        "symbol": symbol,
        "analysis": "",
        "confidence": 0,
        "patterns": [],
        "combined_score": "N/A",
        "error": None,
    }

    # Validate
    if not ANTHROPIC_AVAILABLE or not config.ANTHROPIC_API_KEY:
        result["error"] = "Anthropic API not available"
        return result

    image_path = Path(image_path)
    if not image_path.exists():
        result["error"] = f"Image not found: {image_path}"
        return result

    # Encode image
    image_data = _encode_image(image_path)
    if not image_data:
        result["error"] = "Failed to encode image"
        return result

    # Build prompt
    algo_context = _build_algo_context(scan_result)
    user_prompt = VISION_USER_PROMPT.format(
        symbol=symbol,
        algo_context=algo_context,
    )

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=model,
            max_tokens=800,
            system=VISION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": _get_media_type(image_path),
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                }
            ],
        )

        analysis_text = message.content[0].text
        result["analysis"] = analysis_text

        # Parse confidence score from response
        result["confidence"] = _parse_confidence(analysis_text)

        # Parse detected patterns
        result["patterns"] = _parse_patterns(analysis_text)

        # Combined score with algorithmic data
        if scan_result:
            tt_score = scan_result.get("trend_template_score", 0)
            vcp_algo = scan_result.get("vcp_detected", False)
            visual_conf = result["confidence"]

            # Combined: algorithmic weight 60% + visual 40%
            algo_score = (tt_score / 8) * 10  # normalize to 0-10
            combined = algo_score * 0.6 + visual_conf * 0.4

            result["combined_score"] = f"{combined:.1f}/10"

            # Enhanced verdict
            if combined >= 8 and vcp_algo:
                result["verdict"] = "🟢 STRONG BUY SETUP"
            elif combined >= 6:
                result["verdict"] = "🟡 WATCHLIST — Monitor for breakout"
            elif combined >= 4:
                result["verdict"] = "🟠 NEUTRAL — Base building"
            else:
                result["verdict"] = "🔴 AVOID — Weak setup"
        else:
            result["combined_score"] = f"{result['confidence']}/10 (visual only)"
            result["verdict"] = ""

        log.info(f"Vision: {symbol} analyzed — confidence {result['confidence']}/10, "
                 f"patterns: {result['patterns']}")

    except Exception as e:
        log.error(f"Vision API error for {symbol}: {e}")
        result["error"] = str(e)

    return result


def _parse_confidence(text: str) -> int:
    """Extract visual confidence score (1-10) from Claude's response."""
    import re
    # Look for patterns like "7/10", "Score: 8", "confidence: 9/10"
    patterns = [
        r"(?:confidence|score|tin cậy)[:\s]*(\d+)\s*/\s*10",
        r"(\d+)\s*/\s*10",
        r"(?:confidence|score|tin cậy)[:\s]*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            if 1 <= score <= 10:
                return score
    return 5  # default middle confidence


def _parse_patterns(text: str) -> list[str]:
    """Extract detected pattern names from Claude's response."""
    known_patterns = [
        "VCP", "Volatility Contraction",
        "Cup-with-Handle", "Cup with Handle", "Cup and Handle",
        "Ascending Base", "Flat Base",
        "High Tight Flag", "HTF",
        "Double Bottom", "Triple Bottom",
        "Bull Flag", "Pennant",
        "Breakout", "Pivot",
        "Accumulation", "Tích lũy",
        "Stage 2", "Stage 1",
    ]
    found = []
    text_lower = text.lower()
    for p in known_patterns:
        if p.lower() in text_lower and p not in found:
            found.append(p)
    return found


def format_vision_telegram(vision_result: dict) -> str:
    """Format vision analysis for Telegram message."""
    if vision_result.get("error"):
        return f"👁️ Vision Error: {vision_result['error']}"

    lines = [
        vision_result.get("analysis", "No analysis"),
        "",
        f"📊 Combined Score: *{vision_result.get('combined_score', 'N/A')}*",
    ]

    if vision_result.get("verdict"):
        lines.append(f"📋 Verdict: *{vision_result['verdict']}*")

    if vision_result.get("patterns"):
        lines.append(f"🔍 Patterns: {', '.join(vision_result['patterns'])}")

    return "\n".join(lines)
