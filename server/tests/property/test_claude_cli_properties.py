"""
tests/property/test_claude_cli_properties.py
Property-based tests for claude_cli invariants (hypothesis, 100 examples each).

Properties tested:
  P2: Rate limiting correctness (sliding window)
  P3: Context depth enforcement (FIFO, depth*2 entries max)
  P4: Context token limit enforcement (FIFO, token budget)
  P7: Telegram response length ≤ 4096
  P9: Timeout wall-clock ≤ CLAUDE_CLI_TIMEOUT + 5s  [smoke: mocked]
  P10: Context reset completeness (per-symbol & global)
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from claude_cli.infrastructure import CliInfrastructure, CliResult
from claude_cli.service import ClaudeService, AnalysisRequest, AnalysisResponse, ContextEntry
from claude_cli.telegram_commands import _format_response


# ── helpers ─────────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _success_cli(text: str = "ok [Confidence: 7/10]") -> MagicMock:
    cli = AsyncMock(spec=CliInfrastructure)
    cli.available = True
    cli.invoke = AsyncMock(return_value=CliResult(
        success=True, stdout=text, stderr="", exit_code=0, duration_seconds=0.01
    ))
    return cli


def _make_svc(depth: int = 5, max_tokens: int = 50_000) -> ClaudeService:
    svc = ClaudeService(_success_cli())
    svc._context_depth = depth
    svc._max_context_tokens = max_tokens
    svc._initialized = True
    return svc


# ── P2: Rate Limiting ────────────────────────────────────────────────────────────

@given(
    limit=st.integers(min_value=1, max_value=10),
    extra=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=100)
def test_p2_rate_limit_exactly_n_pass(limit, extra):
    """Exactly `limit` requests pass; the rest are rate-limited."""
    cli = CliInfrastructure(rate_limit=limit, max_parallel=limit + extra + 1, timeout=5)
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)

    total = limit + extra
    results = []

    async def run_all():
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            for _ in range(total):
                results.append(await cli.invoke(prompt="test"))

    asyncio.get_event_loop().run_until_complete(run_all())

    passed = sum(1 for r in results if r.success)
    limited = sum(1 for r in results if r.rate_limited)
    assert passed == limit
    assert limited == extra


# ── P3: Context Depth Enforcement ───────────────────────────────────────────────

@given(
    depth=st.integers(min_value=1, max_value=5),
    interactions=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
def test_p3_context_depth_never_exceeded(depth, interactions):
    """Context per symbol never exceeds depth*2 entries."""
    svc = _make_svc(depth=depth, max_tokens=10_000_000)

    async def run():
        for i in range(interactions):
            await svc.analyze(AnalysisRequest(
                query=f"q{i}", symbol="SYM", include_rag_context=False
            ))

    asyncio.get_event_loop().run_until_complete(run())
    ctx = svc._contexts.get("SYM", [])
    assert len(ctx) <= depth * 2, f"depth={depth}, interactions={interactions}, got {len(ctx)}"


# ── P4: Context Token Budget Enforcement ────────────────────────────────────────

@given(
    max_tokens=st.integers(min_value=10, max_value=500),
    interactions=st.integers(min_value=1, max_value=15),
)
@settings(max_examples=100)
def test_p4_token_budget_never_exceeded(max_tokens, interactions):
    """Total estimated tokens per symbol never exceeds max_tokens after pruning."""
    svc = _make_svc(depth=100, max_tokens=max_tokens)  # depth huge → token is the binding constraint

    async def run():
        for i in range(interactions):
            await svc.analyze(AnalysisRequest(
                query=f"query number {i} with some text",
                symbol="TOK",
                include_rag_context=False,
            ))

    asyncio.get_event_loop().run_until_complete(run())
    ctx = svc._contexts.get("TOK", [])
    total = sum(e.estimated_tokens for e in ctx)
    assert total <= max_tokens, f"max_tokens={max_tokens}, got {total}"


# ── P7: Telegram Response Length ─────────────────────────────────────────────────

@given(
    text=st.text(min_size=0, max_size=10_000),
    source=st.sampled_from(["claude_cli", "anthropic_api", "none"]),
    confidence=st.integers(min_value=0, max_value=10),
    duration=st.floats(min_value=0.0, max_value=120.0, allow_nan=False),
)
@settings(max_examples=100)
def test_p7_telegram_response_never_exceeds_4096(text, source, confidence, duration):
    """Formatted Telegram message is always ≤ 4096 characters."""
    formatted = _format_response(text=text, source=source, confidence=confidence, duration=duration)
    assert len(formatted) <= 4096, f"Message exceeded 4096: len={len(formatted)}"


# ── P9: Timeout Wall-Clock (mocked) ─────────────────────────────────────────────

@given(timeout_secs=st.integers(min_value=1, max_value=3))
@settings(max_examples=5, deadline=None)  # wall-clock test: timeout_secs IS the duration
def test_p9_timeout_wall_clock_bounded(timeout_secs):
    """Wall clock of invoke() does not exceed timeout + 6s even for hanging processes."""
    cli = CliInfrastructure(timeout=timeout_secs, rate_limit=100, max_parallel=5)
    
    mock_proc = AsyncMock()
    mock_proc.returncode = -9
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock(return_value=-9)

    async def hang_communicate(**kwargs):  # accept input=... kwarg
        await asyncio.sleep(999)
        return b"", b""

    mock_proc.communicate = hang_communicate

    async def run():
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            t0 = time.monotonic()
            result = await cli.invoke(prompt="hang")
            elapsed = time.monotonic() - t0
        assert result.timed_out is True
        assert elapsed < timeout_secs + 7  # 5s grace + 2s test headroom

    asyncio.get_event_loop().run_until_complete(run())


# ── P10: Context Reset Completeness ─────────────────────────────────────────────

@given(
    symbols=st.lists(
        st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        min_size=1, max_size=5, unique=True,
    ),
    target_idx=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100)
def test_p10_per_symbol_reset_clears_only_target(symbols, target_idx):
    """reset_context(symbol) clears exactly that symbol, others unchanged."""
    assume(len(symbols) > 0)
    target_idx = target_idx % len(symbols)
    target = symbols[target_idx]

    svc = _make_svc()
    for sym in symbols:
        svc._contexts[sym] = [MagicMock()]

    svc.reset_context(target)

    assert target not in svc._contexts, f"Symbol {target} not cleared"
    for sym in symbols:
        if sym != target:
            assert sym in svc._contexts, f"Symbol {sym} was incorrectly cleared"


@given(
    symbols=st.lists(
        st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        min_size=1, max_size=6, unique=True,
    )
)
@settings(max_examples=100)
def test_p10_global_reset_clears_all(symbols):
    """reset_context('') clears ALL symbol contexts."""
    svc = _make_svc()
    for sym in symbols:
        svc._contexts[sym] = [MagicMock()]

    svc.reset_context("")
    assert svc._contexts == {}, f"Global reset left: {list(svc._contexts.keys())}"
