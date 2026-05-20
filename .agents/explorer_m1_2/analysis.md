# Analysis: Hook Service Startup and Version Mismatch Check

## Core Summary
The startup flow of the Hook Server in `nerves/core/hook_service.py` is analyzed to integrate a non-blocking background check comparing the local `angati.exe` hash against the brain's `angati.exe`. A thread-safe, platform-aware verification and testing strategy is designed to capture and assert the warnings via standard redirection channels without interrupting production server startup.

---

## 1. Hook Service Startup Architecture
The Hook Server is a Python `ThreadingHTTPServer` defined in `nerves/core/hook_service.py`. It boots synchronously inside `main()`:

```python
# nerves/core/hook_service.py (Lines 247-259)
def main():
    port = 9105
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, SRAHookHandler)
    print(f"[SRA Server] Running SRA Hybrid Hook Server on port {port}...", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("[SRA Server] Stopping server...", file=sys.stderr)
```

Because `serve_forever()` blocks the main execution thread, any boot-time configuration checks must be run:
1. **Asynchronously**: Using a background thread (`threading.Thread`) configured as a **daemon** so it does not block server shutdown.
2. **Gracefully**: Safely catching all filesystem or binary reading exceptions so that a failure in checking does not crash the HTTP listener.

---

## 2. Binary Path Resolution
Based on `PROJECT.md` and code references:
*   **Local `angati.exe`**: Typically located at the project root `angati.exe` or `tools/angati/angati.exe`.
*   **Brain `angati.exe`**: Situated under `C:\Users\pesil\.gemini\antigravity\tools\angati\angati.exe`. In Python, this is cleanly represented in a cross-platform manner as `Path.home() / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"`.

To support testing isolation without mutating global paths, we design an environment-override resolution strategy:

| Binary Entity | Default Path Resolution | Environment Override Override |
|---|---|---|
| **Local Binary** | `AGENTS_ROOT / "tools" / "angati" / "angati.exe"` fallback to `AGENTS_ROOT / "angati.exe"` | `ANGATI_LOCAL_EXE_PATH` |
| **Brain Binary** | `Path.home() / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"` | `ANGATI_BRAIN_EXE_PATH` |

---

## 3. Non-Blocking Version Checker Design
The checker runs as a daemon thread and computes the SHA256 of both files. If they exist but differ, it prints a warning to `sys.stderr`. If either file is missing, it returns immediately without raising errors or printing warnings.

### Proposed Code Block:
```python
def check_angati_version_async() -> threading.Thread:
    """
    Asynchronously compares local angati.exe and brain angati.exe hashes.
    Prints warning on sys.stderr on mismatch, fails gracefully on missing files.
    """
    def check_logic():
        try:
            # Local path resolution
            local_path_env = os.environ.get("ANGATI_LOCAL_EXE_PATH")
            if local_path_env:
                local_path = Path(local_path_env)
            else:
                local_path = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
                if not local_path.exists():
                    local_path = AGENTS_ROOT / "angati.exe"

            # Brain path resolution
            brain_path_env = os.environ.get("ANGATI_BRAIN_EXE_PATH")
            if brain_path_env:
                brain_path = Path(brain_path_env)
            else:
                brain_path = Path.home() / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"

            # Graceful exit if files are missing
            if not local_path.is_file() or not brain_path.is_file():
                return

            # Read in chunks to be memory efficient
            def get_sha256(p: Path) -> str:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                return h.hexdigest()

            if get_sha256(local_path) != get_sha256(brain_path):
                print(
                    "[SRA Server] WARNING: Local angati.exe version mismatch detected! Please manually restart the hook server to synchronize the binary.",
                    file=sys.stderr
                )
        except Exception:
            # Absolute safety: never crash the hook service boot sequence
            pass

    t = threading.Thread(target=check_logic, name="AngatiVersionChecker", daemon=True)
    t.start()
    return t
```

---

## 4. Integration Testing Strategy
We design the unit/integration tests to append to `nerves/workers/trading/test_angati_integration.py`. The strategy isolates the file system using Python's `tempfile` module to simulate various matching and mismatching conditions.

### Highlights of the Testing Strategy:
*   **Windows-Safe File Handling**: Temporarily written files are closed using `.close()` before invoking the thread. This is critical on Windows to prevent `PermissionError` due to file locking when concurrent threads attempt to read the file.
*   **Stderr Interception**: Uses `contextlib.redirect_stderr` to route the warning messages to an in-memory `io.StringIO` buffer to assert their existence.
*   **No Flaky Sleep Checks**: The background thread is joined via `.join(timeout=2.0)` inside the tests, ensuring deterministic completion before assertions.
*   **Environment Cleanliness**: `os.environ` updates are managed in a `try...finally` block to ensure stale environment configurations do not bleed into other tests.

Refer to the proposed implementation patches for exact code shapes:
*   `proposed_hook_service.patch`
*   `proposed_test_angati_integration.patch`
