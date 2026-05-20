# Handoff Report - Hook Service Startup Analysis & Test Design

## 1. Observation
*   **Hook Server File**: `nerves/core/hook_service.py` runs a multi-threaded HTTP server using:
    ```python
    # nerves/core/hook_service.py (Lines 247-259)
    def main():
        port = 9105
        server_address = ('', port)
        httpd = ThreadingHTTPServer(server_address, SRAHookHandler)
        print(f"[SRA Server] Running SRA Hybrid Hook Server on port {port}...", file=sys.stderr)
        try:
            httpd.serve_forever()
    ```
*   **Local Binary Resolution**: In `nerves/core/hook_service.py` (lines 120-122), the local binary path resolves to:
    ```python
    angati_exe = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
    if not angati_exe.exists():
        angati_exe = AGENTS_ROOT / "angati.exe"
    ```
*   **Test Setup File**: `nerves/workers/trading/test_angati_integration.py` currently initiates the HTTP server manually in `setUpClass` (lines 45-47) rather than calling `main()`:
    ```python
    cls.httpd = hook_service.ThreadingHTTPServer(cls.server_address, hook_service.SRAHookHandler)
    cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
    cls.server_thread.start()
    ```
*   **Project Specification**: `PROJECT.md` dictates checking local `angati.exe` SHA256 against brain `angati.exe` (nominally at `~/.gemini/antigravity/tools/angati/angati.exe`), warning to `sys.stderr` on mismatch:
    `[SRA Server] WARNING: Local angati.exe version mismatch detected! Please manually restart the hook server to synchronize the binary.`

---

## 2. Logic Chain
1.  **Requirement for Asynchrony**: Because `serve_forever()` in `hook_service.py` blocks the main thread, the version checking procedure must run in a separate background thread (`threading.Thread`) as a daemon. This guarantees that startup of the HTTP service is never delayed or blocked.
2.  **Safety & Fault Tolerance**: To satisfy the constraint of handling missing files gracefully, checking routines must verify existence via `is_file()`. Any unhandled file access exception (e.g. permission issues) must be caught and ignored, keeping the hook service functional under all circumstances.
3.  **Path Decoupling for Isolation**: Testing mismatch conditions requires control over file contents. Directly patching filesystem methods or relying on system-wide paths is fragile. By introducing environment variables (`ANGATI_LOCAL_EXE_PATH`, `ANGATI_BRAIN_EXE_PATH`), tests can dynamically define arbitrary temporary files.
4.  **Windows Lock Avoidance**: On Windows, concurrent file reading on open file objects triggers `PermissionError`. Therefore, temporary test files must write, flush, and explicitly close their writer handles (`temp_file.close()`) before launching the version checker thread.
5.  **Deterministic Test Assertion**: By returning the created thread object from `check_angati_version_async()`, tests can call `.join(timeout=2.0)` to ensure execution has completed synchronously before inspecting the captured stderr output.

---

## 3. Caveats
*   The default path for the brain `angati.exe` assumes the standard user home path (`Path.home() / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"`). On some systems where standard environment variables like `USERPROFILE` or `HOME` are unset, `Path.home()` could raise a `RuntimeError`. This is mitigated by wrapping path calculations in a try-except block inside the background task.
*   Mocking relies on setting/unsetting environment variables during the test lifecycle. Concurrent tests modifying the same environment variables could lead to race conditions; however, this test suite is configured to run sequentially.

---

## 4. Conclusion
A robust design has been developed:
1.  `check_angati_version_async()` is implemented in `hook_service.py` using a daemon thread, resolving local and brain `angati.exe` paths or environment overrides.
2.  It calculates SHA256 hashes using a chunk size of 8192 bytes and emits warnings on `sys.stderr` on mismatch.
3.  A complete integration test strategy is drafted and saved as `.patch` files to allow zero-dependency, Windows-safe testing.

---

## 5. Verification Method
1.  **Apply patches**: The implementing agent should apply the provided patch files (`proposed_hook_service.patch` and `proposed_test_angati_integration.patch`) to the repository:
    ```bash
    git apply .agents/explorer_m1_2/proposed_hook_service.patch
    git apply .agents/explorer_m1_2/proposed_test_angati_integration.patch
    ```
2.  **Run tests**: Run the integration tests using the project's testing harness:
    ```bash
    python -m unittest nerves/workers/trading/test_angati_integration.py
    ```
3.  **Inspect stderr output**: Confirm that the mismatch test prints `[OK] Test 3: Version mismatch warning verified!`, `[OK] Test 4: Version match no-warning verified!`, and `[OK] Test 5: Graceful handle of missing files verified!`.
