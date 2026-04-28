# Welcome to TradingView Project Team

## How We Use Claude

Based on Dinh Viet Dan's usage over the last 30 days:

Work Type Breakdown:
  Build Feature  ████████████████░░░░  80%
  Plan Design    ████░░░░░░░░░░░░░░░░  20%

Top Skills & Commands:
  /autofix-pr   █████░░░░░░░░░░░░░░░  1x/month
  /permissions  █████░░░░░░░░░░░░░░░  1x/month
  /init         █████░░░░░░░░░░░░░░░  1x/month
  /model        █████░░░░░░░░░░░░░░░  1x/month

Top MCP Servers:
  ccd_session  █████░░░░░░░░░░░░░░░  1 call

## Your Setup Checklist

### Codebases
- [ ] TradingViewProject — main workspace (Flask webhook server + Pine Script + MCP bridge)
- [ ] tradingview-mcp — https://github.com/tradesdontlie/tradingview-mcp (Node MCP server bridging Claude Code to TradingView Desktop via Chrome DevTools Protocol)

### MCP Servers to Activate
- [ ] tradingview — local Node MCP server at `tradingview-mcp/src/server.js`. Gives Claude eyes/hands on your TradingView Desktop chart (read indicators, change symbol, write Pine Script, take screenshots). Requires TradingView Desktop running with `--remote-debugging-port=9222`. Add to `~/.claude/.mcp.json`.
- [ ] ccd_session — internal session helper. Ask Dinh Viet Dan for setup instructions / credentials.

### Skills to Know About
- /init — generate `CLAUDE.md` for a fresh repo so Claude has project context loaded automatically. Run this first in any new clone.
- /permissions — review and tune which Bash commands and tools auto-approve in this project. Useful when Claude keeps prompting for the same permission.
- /model — switch the active model (Opus/Sonnet/Haiku) per task. Heavier reasoning → Opus; quick edits → Haiku/Sonnet.
- /autofix-pr — automatically address review comments on a pull request. Run inside the PR branch.

## Team Tips

_TODO_

## Get Started

_TODO_

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->
