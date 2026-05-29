from vision import _parse_confidence, _parse_patterns

text = """
👁️ VISUAL ANALYSIS — TESTUSDT
1. Pattern: I see a Volatility Contraction Pattern (VCP) and a Cup-with-Handle.
2. Trend: Stage 2 uptrend.
3. Volume: Dry-up volume is visible.
4. Confidence: 8/10
"""

conf = _parse_confidence(text)
patterns = _parse_patterns(text)

print(f"Confidence: {conf}")
print(f"Patterns: {patterns}")
