# Plan: TradingView Edge Node Ecosystem Evaluation

This plan outlines the steps, roles, and milestones to perform a comprehensive stability and safety evaluation of the TradingView Edge Node ecosystem.

## Cognitive Role: SRE | E-Factor: E4 (Critical)
The evaluation requires testing under high concurrency, stress, failure states, network protocol connectivity (CDP on 9222), and asynchronous Telegram bot message coordinates.

## Milestones

### Milestone 1: Exploration & System State Audit
- **Goal**: Verify current codebase hooks, test paths, and identify existing scripts or endpoints for Webhook, CDP, and Telegram.
- **Tasks**:
  1. Inspect `nerves/workers/trading/gateway/webhook.py` and `nerves/workers/trading/processor/signal_processor.py`.
  2. Inspect `nerves/workers/trading/telegram_bot.py` and `nerves/workers/trading/hub/notification_hub.py`.
  3. Locate existing tests under `nerves/workers/trading/tests/` that check rate limits, circuit breakers, CDP, and Telegram.
- **Worker**: `teamwork_preview_explorer` (Explorer)

### Milestone 2: Webhook Stability & Circuit Breaker Verification
- **Goal**: Perform stress and boundary testing on the FastAPI webhook to verify concurrency, rate limiting, and circuit breaker isolation.
- **Tasks**:
  1. Verify rate limiting triggers HTTP 429 at 15 req/min and recovers automatically.
  2. Verify unauthorized payloads are rejected (invalid price, format, token).
  3. Verify timeframe circuit breaker isolates non-1H signals (rejections for 4H, 15m, D, etc.).
- **Worker**: `teamwork_preview_worker` (Worker) & `teamwork_preview_challenger` (Challenger)

### Milestone 3: CDP & Telegram Hub Verification
- **Goal**: Audit CDP browser automation connectivity and Telegram interactive approval flow return types.
- **Tasks**:
  1. Verify CDP connection on port 9222 and version JSON.
  2. Audit `send_interactive_trade_approval` in `telegram_bot.py` to ensure it returns `List[Tuple[int, int]]` (coordinates) and not `bool` (SCAR-G2-001).
  3. Verify approval callbacks map correctly to active signal trackers.
- **Worker**: `teamwork_preview_worker` (Worker) & `teamwork_preview_challenger` (Challenger)

### Milestone 4: Forensic Audit & Synthesis
- **Goal**: Perform independent verification of results, check integrity logs, and write the final report.
- **Tasks**:
  1. Review all testing logs and test runner output.
  2. Run `teamwork_preview_auditor` to perform integrity checks.
  3. Synthesize the findings and present the final report.
- **Worker**: `teamwork_preview_reviewer` & `teamwork_preview_auditor`

## Execution Path
Explorer (Milestone 1) -> Worker (Milestone 2 & 3) -> Challenger (Stress/Adversarial validation) -> Reviewers -> Forensic Auditor -> Orchestrator Synthesis -> Done.
