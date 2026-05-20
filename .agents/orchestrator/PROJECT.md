# Project: Angati.exe Version Checking and Warning Mechanism

## Architecture
- **Hook Server**: `nerves/core/hook_service.py` runs a multi-threaded HTTP server intercepting tools (pre-tool, post-tool, etc.). We need to insert a boot-time version checker.
- **Binaries**:
  - Local `angati.exe`: situated at project root or `tools/angati/angati.exe`.
  - Brain `angati.exe`: situated under `C:\Users\pesil\.gemini\antigravity\tools\angati` or similar, which translates to `~/.gemini/antigravity/tools/angati/angati.exe`.
- **Warning Channel**: `sys.stderr` is used for printing SRA Server startup logs (e.g. `[SRA Server] ...`). A mismatch should print a warning.
- **Testing**: `nerves/workers/trading/test_angati_integration.py` or a dedicated test file to verify the check using a mock binary path or subclass/mock implementation.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Design | Find the actual paths of local and brain `angati.exe`, study hook startup, design version check logic | None | DONE |
| 2 | Implementation | Implement non-blocking version checking on startup in `hook_service.py` | M1 | DONE |
| 3 | Automated Testing | Add unit/integration tests to verify mismatch warning and graceful handling of missing files | M2 | DONE |
| 4 | Verification & Audit | Review change correctness, run tests, run integrity audits | M3 | DONE |

## Interface Contracts
- **Version Check Function**:
  - `check_angati_version_async()` -> runs asynchronously in a daemon thread.
  - Compares the SHA256 of the local `angati.exe` against the brain's `angati.exe`.
  - If they differ, prints to `sys.stderr`:
    `[SRA Server] WARNING: Local angati.exe version mismatch detected! Please manually restart the hook server to synchronize the binary.`
  - Handles missing files (either local or brain `angati.exe` absent) without raising exceptions.
- **Test Scenarios**:
  - Mismatched files: triggers warning on stderr.
  - Matching files: no warning.
  - Missing file(s): handles gracefully (no warning, no crash).
