"""
service.py — ClaudeService: business logic for Claude CLI integration.

Responsibilities (Service Layer invariants):
- Single owner of per-symbol conversation context (self._contexts).
- Single decision-maker for CLI → API fallback.
- Assembles prompts from system context, RAG chunks, and conversation history.
- Owns context pruning (by depth and by token budget).
- Never spawns subprocesses directly; calls CliInfrastructure.invoke().
- Context state is ONLY mutated here; Interface layers are read-only consumers.
"""
from __future__ import annotations

import importlib.util
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import config
from .infrastructure import CliInfrastructure, CliResult

log = logging.getLogger(__name__)

ANTHROPIC_AVAILABLE = importlib.util.find_spec("anthropic") is not None

# ─── Public dataclasses ────────────────────────────────────────────────────────


@dataclass
class AnalysisRequest:
    """Input to ClaudeService for any analysis."""
    query: str
    symbol: str = ""
    action: str = ""
    price: Optional[float] = None
    trading_context: Optional[dict] = None  # positions, signals, watchlist
    include_rag_context: bool = True
    image_path: Optional[str] = None


@dataclass
class AnalysisResponse:
    """Output from ClaudeService."""
    text: str
    confidence: int = 5          # 1-10 scale
    source: str = "claude_cli"   # "claude_cli" | "anthropic_api"
    duration_seconds: float = 0.0
    context_tokens_used: int = 0
    error: str = ""


@dataclass
class ContextEntry:
    """Single conversation turn in per-symbol history."""
    role: str             # "user" | "assistant"
    content: str
    timestamp: float
    estimated_tokens: int


# ─── Service class ─────────────────────────────────────────────────────────────

# Minervini SEPA system prompt loaded once at startup
_SEPA_SYSTEM_PROMPT_TEMPLATE = """Bạn là chuyên gia giao dịch theo phương pháp SEPA (Specific Entry Point Analysis) \
của Mark Minervini. Nhiệm vụ của bạn là phân tích các tín hiệu giao dịch và đưa ra khuyến nghị \
dựa trên nguyên tắc SEPA chính xác, ngắn gọn, và có thể hành động ngay.

Nguyên tắc cốt lõi:
- Trend Template: 8 tiêu chí xác nhận Stage 2 uptrend
- VCP (Volatility Contraction Pattern): tìm điểm breakout từ base có volume cạn
- Risk Management: SL tối đa 7-8%, R:R tối thiểu 2.5:1
- Volume xác nhận: breakout cần volume ≥ 150% trung bình 50 phiên
- Không mua khi thị trường chung Stage 3/4 (distribution)

Trả lời NGẮN GỌN (dưới 200 từ), dùng emoji để dễ đọc trên Telegram.
Luôn kết thúc bằng mức confidence 1-10 theo format: [Confidence: X/10]
"""


class ClaudeService:
    """
    Business logic layer for Claude CLI integration.

    Lifecycle:
        svc = ClaudeService(cli)
        await svc.initialize()   # called at app startup
        response = await svc.analyze(request)
        response = await svc.query("explain VCP", symbol="BTCUSDT")

    Property guarantees:
        Property 3: context depth ≤ CLAUDE_CONTEXT_DEPTH per symbol
        Property 4: context token total ≤ CLAUDE_MAX_CONTEXT_TOKENS per symbol
        Property 5: fallback returns structurally identical AnalysisResponse
        Property 10: reset_context() clears exactly what is requested
    """

    def __init__(self, cli: CliInfrastructure):
        self._cli = cli
        self._contexts: dict[str, list[ContextEntry]] = {}
        self._context_depth: int = getattr(config, "CLAUDE_CONTEXT_DEPTH", 5)
        self._max_context_tokens: int = getattr(config, "CLAUDE_MAX_CONTEXT_TOKENS", 50_000)
        self._system_prompt: str = _SEPA_SYSTEM_PROMPT_TEMPLATE
        self._initialized: bool = False

    # ── Lifecycle ───────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """
        Load system prompt, optionally augmenting with top RAG chunks.
        Called once during app startup via lifespan hook.
        """
        if self._initialized:
            return
        try:
            # Try to pull top-K Minervini chunks to enrich the system prompt
            import rag
            chunks = rag.query_knowledge("SEPA Trend Template VCP pivot breakout", n_results=2)
            if chunks:
                extra = "\n\n---\n".join(c["content"][:600] for c in chunks)
                self._system_prompt = (
                    _SEPA_SYSTEM_PROMPT_TEMPLATE
                    + "\n\n## Tham khảo từ Minervini Knowledge Base:\n"
                    + extra
                )
                log.info(f"ClaudeService: system prompt enriched with {len(chunks)} RAG chunks")
        except Exception as exc:
            log.warning(f"ClaudeService: RAG enrichment skipped: {exc}")

        self._initialized = True
        log.info("ClaudeService initialized.")

    # ── Public API ──────────────────────────────────────────────────────────────

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """
        Main entry point for all structured trading analysis requests.

        Steps:
            1. Assemble prompt (system + RAG + context + query)
            2. Try CLI invocation
            3. On failure → fallback to Anthropic SDK (if configured)
            4. Parse confidence from response text
            5. Update per-symbol context
            6. Return AnalysisResponse
        """
        t_start = time.monotonic()
        prompt = await self._assemble_prompt(request)

        # ── Attempt CLI ─────────────────────────────────────────────────
        result: CliResult = await self._cli.invoke(
            prompt=prompt,
            system_prompt=self._system_prompt,
            image_path=request.image_path,
        )

        if result.success:
            text = result.stdout
            confidence = self._parse_confidence(text)
            ctx_tokens = self._total_context_tokens(request.symbol)
            self._update_context(request.symbol, request.query, text)
            return AnalysisResponse(
                text=text,
                confidence=confidence,
                source="claude_cli",
                duration_seconds=result.duration_seconds,
                context_tokens_used=ctx_tokens,
            )

        # CLI failed — decide whether to fallback ───────────────────────
        fallback_enabled = getattr(config, "CLAUDE_CLI_FALLBACK_SDK", True)
        has_api = ANTHROPIC_AVAILABLE and bool(getattr(config, "ANTHROPIC_API_KEY", ""))
        if fallback_enabled and has_api:
            log.info(f"ClaudeService: CLI fail ({result.stderr[:100]}), falling back to SDK")
            resp = await self._fallback_to_api(prompt)
            if resp.text:
                self._update_context(request.symbol, request.query, resp.text)
            resp.duration_seconds = time.monotonic() - t_start
            return resp

        # Both CLI and fallback unavailable ─────────────────────────────
        err_msg = result.stderr or "Claude CLI failed and SDK fallback is disabled."
        log.error(f"ClaudeService: all providers failed: {err_msg[:150]}")
        return AnalysisResponse(
            text=f"⚠️ Phân tích AI không khả dụng: {err_msg[:120]}",
            confidence=0,
            source="none",
            duration_seconds=time.monotonic() - t_start,
            error=err_msg,
        )

    async def query(self, query: str, symbol: str = "") -> AnalysisResponse:
        """Simplified entry for ad-hoc queries without full trading context."""
        return await self.analyze(AnalysisRequest(
            query=query,
            symbol=symbol,
            include_rag_context=False,
        ))

    def reset_context(self, symbol: str = "") -> None:
        """
        Clear conversation context.
        - symbol="": clears ALL symbols (Property 10 global reset).
        - symbol="BTCUSDT": clears only that symbol.
        """
        if symbol:
            cleared = len(self._contexts.pop(symbol, []))
            log.info(f"ClaudeService: context cleared for {symbol} ({cleared} turns)")
        else:
            total = sum(len(v) for v in self._contexts.values())
            self._contexts.clear()
            log.info(f"ClaudeService: ALL context cleared ({total} total turns)")

    def get_context_stats(self) -> dict:
        """Return memory usage stats per symbol."""
        stats: dict = {"symbols": {}}
        for sym, entries in self._contexts.items():
            total_tokens = sum(e.estimated_tokens for e in entries)
            stats["symbols"][sym] = {
                "turns": len(entries),
                "estimated_tokens": total_tokens,
            }
        stats["total_symbols"] = len(self._contexts)
        stats["total_turns"] = sum(len(v) for v in self._contexts.values())
        stats["total_estimated_tokens"] = sum(
            e.estimated_tokens
            for entries in self._contexts.values()
            for e in entries
        )
        return stats

    # ── Private helpers ─────────────────────────────────────────────────────────

    async def _assemble_prompt(self, request: AnalysisRequest) -> str:
        """Build the full prompt: optional RAG context + conversation history + query."""
        parts: list[str] = []

        # RAG context (Minervini chunks)
        if request.include_rag_context:
            try:
                import rag
                query_hint = f"{request.action} {request.symbol} {request.query}"
                chunks = rag.query_knowledge(query_hint.strip(), n_results=2)
                if chunks:
                    rag_text = "\n\n---\n".join(
                        f"[{c['metadata'].get('topic','chunk')} | score={c['relevance_score']:.2%}]\n"
                        + c["content"][:600]
                        for c in chunks
                    )
                    parts.append(f"## Kiến thức Minervini liên quan:\n{rag_text}")
            except Exception as exc:
                log.debug(f"ClaudeService: RAG retrieval skipped in prompt: {exc}")

        # Trading context (positions, signals)
        if request.trading_context:
            ctx_lines = []
            for k, v in request.trading_context.items():
                ctx_lines.append(f"- {k}: {v}")
            if ctx_lines:
                parts.append("## Bối cảnh giao dịch:\n" + "\n".join(ctx_lines))

        # Symbol + action metadata
        if request.symbol:
            meta = [f"Symbol: {request.symbol}"]
            if request.action:
                meta.append(f"Action: {request.action.upper()}")
            if request.price is not None:
                meta.append(f"Price: {request.price}")
            parts.append("## Tín hiệu:\n" + " | ".join(meta))

        # Conversation history for this symbol
        history = self._contexts.get(request.symbol or "__global__", [])
        if history:
            hist_lines = []
            for entry in history[-self._context_depth:]:
                tag = "User" if entry.role == "user" else "Claude"
                hist_lines.append(f"[{tag}]: {entry.content[:400]}")
            parts.append("## Lịch sử hội thoại:\n" + "\n".join(hist_lines))

        # The actual query
        parts.append(f"## Câu hỏi / Yêu cầu:\n{request.query}")

        return "\n\n".join(parts)

    async def _fallback_to_api(self, prompt: str) -> AnalysisResponse:
        """
        Use the anthropic Python SDK as fallback (Property 5: transparent source field).
        """
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            t0 = time.monotonic()
            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=512,
                system=self._system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text
            duration = time.monotonic() - t0
            return AnalysisResponse(
                text=text,
                confidence=self._parse_confidence(text),
                source="anthropic_api",
                duration_seconds=duration,
            )
        except Exception as exc:
            log.error(f"ClaudeService: SDK fallback also failed: {exc}")
            return AnalysisResponse(
                text=f"⚠️ AI không khả dụng (CLI + SDK đều lỗi): {str(exc)[:100]}",
                confidence=0,
                source="none",
                error=str(exc),
            )

    def _update_context(self, symbol: str, query: str, response: str) -> None:
        """Append a user+assistant turn to symbol context, then prune."""
        key = symbol or "__global__"
        if key not in self._contexts:
            self._contexts[key] = []

        self._contexts[key].append(ContextEntry(
            role="user",
            content=query,
            timestamp=time.monotonic(),
            estimated_tokens=self._estimate_tokens(query),
        ))
        self._contexts[key].append(ContextEntry(
            role="assistant",
            content=response,
            timestamp=time.monotonic(),
            estimated_tokens=self._estimate_tokens(response),
        ))
        self._prune_context(key)

    def _prune_context(self, symbol: str) -> None:
        """
        Remove oldest entries until both:
          - len(entries) ≤ 2 × CLAUDE_CONTEXT_DEPTH  (turns = user+assistant pairs)
          - total estimated tokens ≤ CLAUDE_MAX_CONTEXT_TOKENS

        Property 3 & 4 guarantees.
        """
        entries = self._contexts.get(symbol, [])
        max_turns = self._context_depth * 2  # each depth unit = 1 user + 1 assistant

        # Depth pruning
        while len(entries) > max_turns:
            entries.pop(0)

        # Token budget pruning
        while entries and self._total_context_tokens_for(entries) > self._max_context_tokens:
            entries.pop(0)

        self._contexts[symbol] = entries

    def _total_context_tokens(self, symbol: str) -> int:
        return self._total_context_tokens_for(self._contexts.get(symbol or "__global__", []))

    @staticmethod
    def _total_context_tokens_for(entries: list[ContextEntry]) -> int:
        return sum(e.estimated_tokens for e in entries)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: chars / 4 (conservative, skewed for mixed EN/VI)."""
        return max(1, len(text) // 4)

    @staticmethod
    def _parse_confidence(text: str) -> int:
        """
        Extract confidence from text matching patterns like:
            [Confidence: 7/10]  or  Confidence: 8/10  or  độ tin cậy: 6
        Returns integer 1–10, defaults to 5 if not found.
        """
        patterns = [
            r"\[Confidence:\s*(\d+)/10\]",
            r"Confidence:\s*(\d+)/10",
            r"độ\s*tin\s*cậy:\s*(\d+)",
            r"\b(\d+)/10\b",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                return max(1, min(10, val))
        return 5
