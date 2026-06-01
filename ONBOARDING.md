# Welcome to TradingView Project

## How We Use Claude

Based on Dinh Viet Dan's usage over the last 30 days:

Work Type Breakdown:
  Build Feature     ████████████████████  67%
  Improve Quality   █████████░░░░░░░░░░░  33%

Top Skills & Commands:
  /autofix-pr        ████████████████████  1x/month
  /permissions       ████████████████████  1x/month
  /init              ████████████████████  1x/month
  /loop              ████████████████████  1x/month
  /model             ████████████████████  1x/month

Top MCP Servers:
  tradingview        ████████████████████  293 calls
  ccd_session        ░░░░░░░░░░░░░░░░░░░░  2 calls

## Your Setup Checklist

### Codebases
- [ ] tradingviewproject — https://github.com/dinhvietdan88-commits/tradingviewproject (main workspace: Pine Script v1/v2, docs, and the `tradingview-mcp/` bridge)

### MCP Servers to Activate
- [ ] tradingview — Reads and controls a live TradingView Desktop chart (78 tools: chart state, Pine Script dev, screenshots, replay, alerts). Local Node server at `tradingview-mcp/`. Requires TradingView Desktop running with `--remote-debugging-port=9222` — use the `/tv-start` skill to launch it. Wire into `~/.claude/.mcp.json`.
- [ ] ccd_session — Internal session helper, used lightly. Ask Dinh Viet Dan for setup details.

### Skills to Know About
- /tv-start — Launch TradingView Desktop with CDP port 9222 (skip if already running). Run this before any `tradingview` MCP work.
- /init — Generate `CLAUDE.md` for a fresh repo so Claude loads project context automatically. Run first in any new clone.
- /permissions — Review/tune which Bash commands and tools auto-approve. Useful when Claude keeps prompting for the same permission.
- /model — Switch the active model per task. Heavier reasoning → Opus; quick edits → Haiku/Sonnet.
- /loop — Run a prompt or slash command on a recurring interval (e.g. `/loop 5m /foo`). Used for polling or babysitting long jobs.
- /autofix-pr — Automatically address review comments on a pull request. Run inside the PR branch.

## Team Tips

- Pine v1 is still under active development — don't treat it as archived. Both `pine/v1` and `pine/v2` are live.
- Always run `/tv-start` before any `tradingview` MCP work so the chart is reachable on CDP port 9222.

## Get Started

- Read `docs/knowledge/trading_wizard/README.md` to get oriented on the Minervini SEPA knowledge base that drives a lot of the strategy work here.

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
