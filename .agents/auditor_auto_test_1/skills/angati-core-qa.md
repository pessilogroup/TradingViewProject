# Angati Core QA

## Overview

Full automated quality assurance pipeline for Angati satellite Python core files.
Covers: syntax, lint, security patterns, auto-fix, and integration test verification.

## Quick Start

```
# QA a list of files
uv run scripts/qa_core.py check --files nerves/core/hook_service.py nerves/core/core_scar_memory.py

# Fix all auto-fixable issues
uv run scripts/qa_core.py fix --files nerves/core/hook_service.py

# Run full pipeline (check + fix + re-verify + test)
uv run scripts/qa_core.py full --files nerves/core/core_scar_memory.py nerves/core/hook_service.py
```

## Utility Scripts

### `scripts/qa_core.py`

| Subcommand | Arguments | Description |
|---|---|---|
| `check` | `--files FILE [FILE...]` | Run all checks without modifying files |
| `fix` | `--files FILE [FILE...]` | Auto-fix all fixable issues via ruff |
| `full` | `--files FILE [FILE...]` | Full pipeline: check + fix + re-verify |
| `report` | `--files FILE [FILE...]` `--output FILE` | Generate QA report to file |

### Check Pipeline (in order)

1. **`py_compile`** — Syntax validation. Hard fail if any file fails.
2. **`ruff check`** — Style + lint (E, W, F rules). Counts errors, lists fixable vs manual.
3. **AST Audit** — Security/design pattern scan:
   - `[CRITICAL]` Bare `except:` clauses
   - `[HIGH]` `subprocess.run` missing `timeout=`
   - `[MEDIUM]` `try/except/pass` (silent exception swallowing)
   - `[MEDIUM]` Stub functions (body is only `pass`, no return)
   - `[MEDIUM]` Unused local variables in function scope
4. **`ruff check --fix`** — Auto-fix all fixable issues (E401, F401, F541, W293...)
5. **Integration test** — Run `test_angati_integration.py` if present

## Workflow

### Step 1: Identify Files
- Accept explicit file list from user
- Or auto-detect all `*.py` files under `nerves/core/`

### Step 2: Syntax Gate
- Run `python -m py_compile FILE...`
- If any file fails, STOP and report — cannot continue with broken syntax

### Step 3: Ruff Lint
- Run `python -m ruff check FILE... --output-format=concise`
- Count total errors and fixable errors
- Note: E402 on intentional deferred imports should be suppressed with `# noqa: E402`

### Step 4: AST Security Scan
- Run `scripts/qa_core.py check --files FILE...`
- Any `[CRITICAL]` finding must be fixed before proceeding
- `[HIGH]` findings should be fixed (subprocess timeout)
- `[MEDIUM]` and `[STYLE]` are best-effort

### Step 5: Auto-Fix
- Run `python -m ruff check --fix --unsafe-fixes FILE...`
- Then re-run ruff to verify 0 errors remain
- For 2 remaining E402 on intentional deferred imports: add `# noqa: E402` with comment

### Step 6: Re-Verify
- Run `python -m py_compile` again to confirm no regressions
- Run `python -m ruff check` to confirm 0 errors

### Step 7: Integration Test
- Run `python nerves/workers/trading/test_angati_integration.py`
- Expected output: `Ran 2 tests in ~2s — OK`

### Step 8: Report
- Generate QA report markdown documenting all issues found and fixed

## Common Mistakes

1. **Running `ruff --fix` without re-verifying**: Always re-run `ruff check` after auto-fix to confirm 0 errors remain. Ruff sometimes reports "fixed X" but leaves unfixable issues.

2. **Ignoring `subprocess.run` timeout**: Any subprocess calling `angati.exe` without `timeout=` risks hanging the hook server indefinitely. Always add `timeout=` and `except subprocess.TimeoutExpired`.

3. **Confusing intentional E402 with bugs**: `import core_env_loader` and `import os` in `core_scar_memory.py` MUST come after `sys.path.insert()` and `env_loader.load()`. These are not bugs — suppress with `# noqa: E402` and add a comment explaining the design intent.
