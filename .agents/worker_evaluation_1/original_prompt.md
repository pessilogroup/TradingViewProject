## 2026-05-20T22:14:04Z

You are the worker responsible for implementing the fix and running verification tests for the TradingView Edge Node ecosystem evaluation.

Your task is to:
1. Fix the path mismatch bug in `nerves/workers/trading/mcp_client.py` on line 20: replace `Path(__file__).parent.parent / "tradingview-mcp"` with `Path(__file__).parent.parent.parent.parent / "tradingview-mcp"`.
2. Run `python nerves/workers/trading/scripts/test_cdp.py` and verify that the output no longer prints "TradingView MCP not found", but instead attempts to perform a health check (it will print `connected: False` or similar connection failure, which is expected since the TradingView Desktop app is not running).
3. Run the full test suite using `pytest nerves/workers/trading/tests/` and verify that all tests pass successfully.
4. Verify that Webhook concurrency, auth gating, 15 req/min rate limits, timeframe circuit breakers, and Telegram bot message coordinate compliance (SCAR-G2-001) are thoroughly tested and passing.
5. Write your execution report and findings, including actual command output, to `C:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_evaluation_1\handoff.md`.
