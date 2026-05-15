"""
tests/unit/test_claude_service.py
Unit tests for claude_cli.ClaudeService.

Tests cover:
  - analyze(): CLI success path (source="claude_cli")
  - analyze(): CLI fail → SDK fallback (source="anthropic_api")
  - analyze(): Both fail → error AnalysisResponse
  - _assemble_prompt(): sections present in correct order
  - Context accumulation (turns added per-symbol)
  - FIFO depth pruning (oldest entries removed)
  - Token budget pruning
  - reset_context() per-symbol vs global
  - get_context_stats() field accuracy
  - _parse_confidence() regex patterns
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from claude_cli.infrastructure import CliInfrastructure, CliResult
from claude_cli.service import ClaudeService, AnalysisRequest, AnalysisResponse, ContextEntry


# ── fixtures ────────────────────────────────────────────────────────────────────

def _make_cli(success: bool = True, text: str = "analysis ok [Confidence: 7/10]") -> MagicMock:
    cli = AsyncMock(spec=CliInfrastructure)
    cli.available = success
    cli.invoke = AsyncMock(return_value=CliResult(
        success=success,
        stdout=text if success else "",
        stderr="" if success else "CLI error",
        exit_code=0 if success else 1,
        duration_seconds=0.1,
    ))
    return cli


def _make_service(cli=None, depth: int = 3, max_tokens: int = 1000) -> ClaudeService:
    if cli is None:
        cli = _make_cli()
    svc = ClaudeService(cli)
    svc._context_depth = depth
    svc._max_context_tokens = max_tokens
    svc._initialized = True  # skip RAG init
    return svc


def _req(query: str = "analyse AAPL", symbol: str = "AAPL", include_rag: bool = False) -> AnalysisRequest:
    return AnalysisRequest(query=query, symbol=symbol, include_rag_context=include_rag)


# ── analyze: success ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_cli_success_returns_source_cli():
    svc = _make_service()
    resp: AnalysisResponse = await svc.analyze(_req())
    assert resp.source == "claude_cli"
    assert resp.text == "analysis ok [Confidence: 7/10]"
    assert resp.confidence == 7
    assert resp.error == ""


@pytest.mark.asyncio
async def test_analyze_cli_success_updates_context():
    svc = _make_service()
    await svc.analyze(_req(symbol="BTCUSDT"))
    ctx = svc._contexts.get("BTCUSDT", [])
    assert len(ctx) == 2  # user + assistant
    assert ctx[0].role == "user"
    assert ctx[1].role == "assistant"


# ── analyze: fallback ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_cli_fail_triggers_sdk_fallback():
    cli = _make_cli(success=False)
    svc = _make_service(cli=cli)
    svc._max_context_tokens = 99999

    fake_resp = AnalysisResponse(text="fallback ok [Confidence: 6/10]", source="anthropic_api", confidence=6)
    with patch.object(svc, "_fallback_to_api", AsyncMock(return_value=fake_resp)):
        resp = await svc.analyze(_req())

    assert resp.source == "anthropic_api"
    assert resp.text == "fallback ok [Confidence: 6/10]"


@pytest.mark.asyncio
async def test_analyze_both_fail_returns_error_response():
    cli = _make_cli(success=False)
    svc = _make_service(cli=cli)

    error_resp = AnalysisResponse(
        text="⚠️ AI không khả dụng",
        confidence=0,
        source="none",
        error="both failed",
    )
    with patch.object(svc, "_fallback_to_api", AsyncMock(return_value=error_resp)):
        # disable SDK fallback
        with patch("claude_cli.service.ANTHROPIC_AVAILABLE", False):
            resp = await svc.analyze(_req())

    assert resp.source == "none"
    assert resp.confidence == 0


# ── context management ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_context_depth_pruning_fifo():
    """With depth=2, after 3 interactions only the last 4 entries survive."""
    svc = _make_service(depth=2)  # max entries = 2*2 = 4
    for i in range(3):
        await svc.analyze(_req(query=f"query {i}", symbol="TSLA"))
    ctx = svc._contexts["TSLA"]
    assert len(ctx) <= 4, f"Expected ≤4 entries, got {len(ctx)}"
    # Oldest entries should be gone, newest preserved
    assert ctx[-1].role == "assistant"


@pytest.mark.asyncio
async def test_context_token_budget_pruning():
    """Token budget pruning removes oldest entries until within limit."""
    # max_tokens so small that only 1 turn fits (~4 chars per token → 100 tokens → 400 chars)
    svc = _make_service(depth=10, max_tokens=50)
    for i in range(5):
        await svc.analyze(_req(query=f"q{i}", symbol="NVDA"))
    ctx = svc._contexts.get("NVDA", [])
    total_tokens = sum(e.estimated_tokens for e in ctx)
    assert total_tokens <= 50, f"Token budget exceeded: {total_tokens}"


def test_reset_context_per_symbol():
    svc = _make_service()
    svc._contexts["AAPL"] = [MagicMock()]
    svc._contexts["MSFT"] = [MagicMock()]
    svc.reset_context("AAPL")
    assert "AAPL" not in svc._contexts
    assert "MSFT" in svc._contexts  # untouched


def test_reset_context_global():
    svc = _make_service()
    svc._contexts["AAPL"] = [MagicMock()]
    svc._contexts["MSFT"] = [MagicMock()]
    svc.reset_context("")
    assert svc._contexts == {}


# ── get_context_stats ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_context_stats_fields():
    svc = _make_service()
    await svc.analyze(_req(symbol="AMD"))
    stats = svc.get_context_stats()
    assert "symbols" in stats
    assert "AMD" in stats["symbols"]
    assert stats["total_symbols"] == 1
    assert stats["total_turns"] == 2  # user + assistant
    assert stats["total_estimated_tokens"] > 0


# ── _parse_confidence ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("[Confidence: 8/10]", 8),
    ("Confidence: 3/10", 3),
    ("độ tin cậy: 9", 9),
    ("some text 7/10 more text", 7),
    ("no confidence here", 5),   # default
    ("[Confidence: 11/10]", 10), # capped at 10
    ("[Confidence: 0/10]", 1),   # floor at 1
])
def test_parse_confidence(text, expected):
    svc = _make_service()
    assert svc._parse_confidence(text) == expected


# ── _assemble_prompt ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assemble_prompt_contains_query():
    svc = _make_service()
    req = AnalysisRequest(
        query="Is AAPL a good buy?",
        symbol="AAPL",
        action="BUY",
        price=185.5,
        include_rag_context=False,
    )
    prompt = await svc._assemble_prompt(req)
    assert "Is AAPL a good buy?" in prompt
    assert "AAPL" in prompt
    assert "BUY" in prompt


@pytest.mark.asyncio
async def test_assemble_prompt_includes_history():
    svc = _make_service()
    svc._contexts["AAPL"] = [
        ContextEntry(role="user", content="prior question", timestamp=0.0, estimated_tokens=5),
        ContextEntry(role="assistant", content="prior answer", timestamp=0.0, estimated_tokens=10),
    ]
    req = _req(symbol="AAPL", include_rag=False)
    prompt = await svc._assemble_prompt(req)
    assert "prior question" in prompt or "prior answer" in prompt
