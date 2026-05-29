## 2026-05-27T12:14:01Z
You are TV CDP Discovery Explorer. Your task is to investigate how to connect to TradingView Desktop via Chrome DevTools Protocol (CDP) on port 9222.
Specifically:
1. Examine `scripts/launch_tv_msix_cdp.ps1` and find standard paths for TradingView Desktop on Windows (both standard install and MSIX store).
2. Examine the health check code in `nerves/workers/trading/mcp_client.py` and see how it tests connection to port 9222.
3. Formulate the exact logic required in Python (or using PowerShell) to automatically detect if TradingView is running, locate the binary if not, and launch it with `--remote-debugging-port=9222` (including MSIX resolution via `Get-AppxPackage`).
Write your analysis and findings to `c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_m1_1\analysis.md`. Include a list of verified commands or Python code snippets for launching and health-checking.
