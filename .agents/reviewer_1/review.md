# Review Report: Angati Version Checking Mechanism

## Verdict: PASS

## 🔎 Scope of Review
The following files were inspected and tested:
1. `nerves/core/hook_service.py` (specifically lines 247-315, containing `check_angati_version_async` and `main` setup)
2. `nerves/workers/trading/test_angati_integration.py` (specifically lines 121-222, containing version checking unit tests)

---

## 🛠️ Verification Execution
The integration test suite was run on Windows using PowerShell:

### Command Line Invocation
```powershell
python -m unittest nerves/workers/trading/test_angati_integration.py
```

### Output Log
```
[SRA Server] Eagerly warming up FastEmbed model in RAM...
[SRA Server] FastEmbed model loaded successfully.
.....
----------------------------------------------------------------------
Ran 5 tests in 2.039s

OK
Ingesting: 'Test Integration Event - 1779313157'
[OK] Ingestion verified in table 'memories': ('006ea57f-4cd7-4f92-b7cf-225e37838e83', 'Test Integration Event - 1779313157', 'Test Integration Event - 1779313157', None, '{"category":"test_run","source":"angati_cli"}', '2026-05-20 21:39:17', '')
[OK] Test 2: Background Semantic Ingestion verified!
[OK] Test 1: SRA Server Health Endpoint passed!
```
All 5 tests passed successfully.

---

## 📋 Dimension Analysis

### 1. Correctness
- **Logic Verification**: The hashing function successfully calculates the SHA-256 digests of the local and brain binaries and correctly prints the mismatch message to `sys.stderr` when they differ.
- **Environment Overrides**: Standard environment overrides (`ANGATI_LOCAL_EXE_PATH` and `ANGATI_BRAIN_EXE_PATH`) are honored properly, allowing precise control in container or testing settings.
- **Hash Chunking**: The code hashes the binary in 64KB chunks (`65536` bytes), ensuring O(1) memory usage regardless of binary size.

### 2. Safety & Boot Resilience
- **Non-blocking Execution**: The version check executes asynchronously inside a background daemon thread (`daemon=True`). If files are slow to resolve or hash, SRA Server boot is unaffected, avoiding deadlock or timeout failures.
- **Exception Isolation**: The hashing function `get_sha256` wraps all filesystem operations in a generic `try ... except Exception: return None` block. This prevents file locking or read permissions from causing boot crashes.
- **Thread Safety**: The version checking thread operates independently, performing read-only file scans and logging warnings, which requires no synchronization write-locks.

### 3. Clean Imports
- **Standard Library Only**: Within the version check code path, only standard library modules (`os`, `hashlib`, `threading`, `pathlib`) are imported. This guarantees zero external package dependencies on startup.

### 4. Resource Cleanup
- **File Closing**: Hashing uses a context manager (`with open(p, "rb") as f:`), guaranteeing that the file handles are closed immediately after reading is finished.
- **Temporary Files in Tests**: The tests create temporary files with `delete=False` and close them before execution, preventing Windows file-locking issues. Cleanups are reliably performed in `finally` blocks using `os.unlink()`.

### 5. Windows Compatibility
- **Path Resolution**: The code uses Python `pathlib.Path` objects to construct paths, automatically adapting to Windows backslashes (`\`).
- **File Access Safety**: Explicitly closing file objects before unlinking them is critical for Windows, which prevents `PermissionError` when deleting temp files.
- **Encoding Tolerances**: Test files configure stdout/stderr encoding to UTF-8 using `reconfigure(encoding='utf-8', errors='ignore')` where supported, mitigating encoding mismatch crashes on legacy Windows command shells.

---

## ⚡ Adversarial Challenge (Stress-Testing)

### Scenario 1: Extremely Large Binaries
- *Scenario*: One or both `angati.exe` paths are set to points of massive files (e.g. 5GB).
- *Result*: The chunked reader limits RAM usage to 64KB. Since the execution is offloaded to a background thread, the SRA Server boots and serves requests immediately, avoiding any service disruption.

### Scenario 2: Severe Permission Restrictions / File Locking
- *Scenario*: The user runs the SRA server as a restricted user, or the binary is locked exclusively by another process.
- *Result*: `open(p, "rb")` throws an `OSError` / `PermissionError`. The inner `try-except` catches this and returns `None`, skipping the warning without throwing any fatal exceptions.

### Scenario 3: `Path.home()` Failure in Constrained Environments
- *Scenario*: In rare environments (e.g., bare minimal scratch containers), `Path.home()` might raise a `RuntimeError` due to missing environment variables.
- *Result*: If `Path.home()` raises an exception, the daemon thread will exit with a traceback printed to stderr, but it will not impact the main HTTP server thread. (Minor risk: stderr noise).
