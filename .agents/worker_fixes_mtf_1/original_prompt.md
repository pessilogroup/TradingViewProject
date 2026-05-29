# Worker Fixes MTF 1 Task

Implement resilience fixes for Multi-Timeframe (MTF) Nested Chart Inset Layouts.

## Mandatory Rules
- DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Problem Statement
Reviewer 2 and the Challenger subagent identified a critical issue:
"A major finding is that a failure to retrieve parent timeframe candles (e.g. due to connection/API issues) will fail the entire concurrent gather fetch, blocking the primary chart render."

## Requirements
1. Modify `nerves/workers/trading/capture_client.py` (specifically where concurrent fetching is done using `asyncio.gather` or similar) to ensure that if the parent timeframe candle fetching raises an exception or fails, it is caught gracefully (e.g., logging a warning/error and setting `parent_candles = None`), allowing the child candle fetching to proceed and the primary chart to render correctly as a single chart without nested insets.
2. Add a new unit test in `tests/unit/test_mtf_nested.py` specifically verifying this resilience (e.g., mock the parent fetch to raise an exception, and assert that the capture call still returns the primary chart's data and renders successfully without crashing).
3. Run the full test suite to ensure all unit and integration tests continue to pass.

Write your report to `changes.md` and handoff report to `handoff.md` with the commands used and verification outputs.
