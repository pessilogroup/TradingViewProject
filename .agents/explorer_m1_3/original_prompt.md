## 2026-05-27T12:14:02Z
You are Webhook Integration Explorer. Your task is to inspect the webhook ingress and persistence layers.
Specifically:
1. Find where the `/webhook` endpoint is implemented (e.g. `nerves/workers/trading/gateway/webhook.py` or `main.py`).
2. Analyze the expected Pydantic schema or payload requirements (e.g. `nerves/workers/trading/data/tv_models.py`). What are the exact fields, data types, and values expected?
3. Inspect how webhook signals are validated (authentication/secrets, IP rate limits).
4. Verify the database persistence structure. Where is the SQLite database located, and what is the schema of the `indicator_signals` table? How are entries inserted into this table?
Write your analysis and findings to `c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_m1_3\analysis.md`.
