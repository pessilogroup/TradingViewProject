# Analysis: Angati.exe Version Checking and Warning Mechanism Design

## 1. Executive Summary
This report analyzes the design and implementation of a boot-time version checker for `angati.exe` inside the `hook_service.py` component. The design outlines a robust, non-blocking check function that uses a background daemon thread to resolve the file paths, compute and compare SHA-256 hashes in a chunked manner, handle missing files gracefully without warning or crashing, and print a warning message to `sys.stderr` when a mismatch is detected.

## 2. Problem Statement & Context
The hook server `nerves/core/hook_service.py` is a crucial asset that intercepts agent tools to evaluate security policies (KG Guard) and failure recovery states (Scar Memory). Both policies rely on executing a binary named `angati.exe`. If the local version of `angati.exe` differs from the main Brain version (situated in the user's App Data directory), inconsistencies might arise.
Therefore, on hook server boot, we must compare the two files:
- **Local `angati.exe`**: situated at project root or `tools/angati/angati.exe`.
- **Brain `angati.exe`**: situated under the user's App Data directory (e.g. `C:\Users\pesil\.gemini\antigravity\tools\angati\angati.exe` or `~/.gemini/antigravity/tools/angati/angati.exe`).

Because `hook_service.py` runs a blocking HTTP server (`serve_forever()`), the check must run **non-blocking** on boot to prevent delaying server startup.

## 3. Path Resolution Strategy
To ensure robustness, the paths to both binaries are resolved dynamically:
- For the local binary, we look at several common project layout locations relative to the `AGENTS_ROOT` directory.
- For the brain binary, we resolve the user's home directory (e.g., via `Path.home()` or the `USERPROFILE` environment variable on Windows).

```python
from pathlib import Path
import os

def resolve_local_angati_path(agents_root: Path) -> Path:
    """Dynamically resolve the local angati.exe path within the project workspace."""
    local_paths = [
        agents_root / "angati.exe",
        agents_root / "tools" / "angati" / "angati.exe",
        agents_root / "spine" / "angati" / "angati.exe"
    ]
    for path in local_paths:
        if path.is_file():
            return path
    return agents_root / "angati.exe"  # Default fallback path

def resolve_brain_angati_path() -> Path:
    """Dynamically resolve the brain's angati.exe path under App Data directory."""
    # 1. Environment variable override (good for testing)
    env_override = os.environ.get("ANGATI_BRAIN_PATH")
    if env_override:
        return Path(env_override)
        
    # 2. Standard location based on user profile / home directory
    home_dir = Path.home()
    standard_path = home_dir / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"
    if standard_path.is_file():
        return standard_path
        
    # 3. Explicit check on Windows fallback environment variable
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        win_path = Path(userprofile) / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"
        if win_path.is_file():
            return win_path
            
    return standard_path
```

## 4. Hashing & Graceful Failure Handling Design
To handle large files efficiently and minimize memory overhead, the hashing logic processes files in chunk sizes (e.g. 64 KB) using Python's `hashlib.sha256()`.

If either the local or brain `angati.exe` is missing:
- The check function **must not crash** (by catching exceptions).
- The check function **must not issue warnings** (it exits silently).
This ensures that systems without local or brain binaries (e.g. clean checkouts, non-Windows environments without full daemon installations) run without any friction.

```python
import hashlib
import sys

def get_file_sha256(file_path: Path) -> str:
    """Calculate SHA-256 of a file using memory-efficient chunking."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):  # Read in 64KB chunks
            sha256.update(chunk)
    return sha256.hexdigest()

def check_angati_version_sync(local_path: Path, brain_path: Path) -> None:
    """Synchronous core logic comparing file hashes and logging mismatches."""
    try:
        # Graceful handling of missing files: exit silently
        if not local_path.is_file() or not brain_path.is_file():
            return
            
        local_hash = get_file_sha256(local_path)
        brain_hash = get_file_sha256(brain_path)
        
        if local_hash != brain_hash:
            # Print version mismatch warning to stderr
            print(
                "[SRA Server] WARNING: Local angati.exe version mismatch detected! "
                "Please manually restart the hook server to synchronize the binary.",
                file=sys.stderr,
                flush=True
            )
    except Exception:
        # Prevent any exceptions from crashing the hook server boot process
        pass
```

## 5. Threading vs. Async Design
Since `hook_service.py` is implemented using a synchronous multi-threaded HTTP server (`ThreadingHTTPServer` with `serve_forever()`), a daemon thread is the safest and most standard pattern for non-blocking operations. An `asyncio` event loop is not run by default in `hook_service.py`, making thread execution the clear choice.

### Thread-based implementation:
```python
import threading

def check_angati_version_async(agents_root: Path) -> None:
    """Launches the version checking logic inside a daemon thread on boot."""
    def run_check():
        local_path = resolve_local_angati_path(agents_root)
        brain_path = resolve_brain_angati_path()
        check_angati_version_sync(local_path, brain_path)
        
    thread = threading.Thread(target=run_check, name="AngatiVersionChecker", daemon=True)
    thread.start()
```

### Asyncio task design (alternative for async event loop environments):
If the hook server were migrated to an async framework (e.g. FastAPI/Uvicorn), blocking file operations should run in an executor:
```python
import asyncio

async def check_angati_version_asyncio(agents_root: Path) -> None:
    """Asynchronous version check running blocking I/O in a thread pool executor."""
    loop = asyncio.get_running_loop()
    local_path = resolve_local_angati_path(agents_root)
    brain_path = resolve_brain_angati_path()
    
    # Run synchronous hash check in thread executor
    await loop.run_in_executor(
        None, 
        check_angati_version_sync, 
        local_path, 
        brain_path
    )
```

## 6. Draft Implementation
Below is the draft implementation of version checking, to be placed inside `hook_service.py` and run on boot during `main()`.

### Code Draft snippet for `nerves/core/hook_service.py`
```python
# Insert at imports section:
# import os
# import hashlib
# import threading
# from pathlib import Path

def get_file_sha256(file_path: Path) -> str:
    """Computes the SHA-256 hash of a file in 64KB chunks."""
    sha = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()
    except Exception:
        return ""

def check_angati_version_async(agents_root: Path) -> None:
    """Starts a non-blocking background thread to check angati.exe version match."""
    def _run():
        try:
            # 1. Resolve local path
            local_paths = [
                agents_root / "angati.exe",
                agents_root / "tools" / "angati" / "angati.exe",
                agents_root / "spine" / "angati" / "angati.exe"
            ]
            local_path = None
            for p in local_paths:
                if p.is_file():
                    local_path = p
                    break
            
            # 2. Resolve brain path
            env_override = os.environ.get("ANGATI_BRAIN_PATH")
            if env_override:
                brain_path = Path(env_override)
            else:
                brain_path = Path.home() / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"
                if not brain_path.is_file():
                    userprofile = os.environ.get("USERPROFILE")
                    if userprofile:
                        win_path = Path(userprofile) / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"
                        if win_path.is_file():
                            brain_path = win_path
            
            # Graceful check for missing files (neither exists -> exit silently)
            if not local_path or not local_path.is_file() or not brain_path.is_file():
                return
                
            local_hash = get_file_sha256(local_path)
            brain_hash = get_file_sha256(brain_path)
            
            if local_hash and brain_hash and local_hash != brain_hash:
                print(
                    "[SRA Server] WARNING: Local angati.exe version mismatch detected! "
                    "Please manually restart the hook server to synchronize the binary.",
                    file=sys.stderr,
                    flush=True
                )
        except Exception:
            pass  # Ensure server never crashes due to background checking logic

    thread = threading.Thread(target=_run, name="AngatiVersionChecker", daemon=True)
    thread.start()
```

### Integration in hook_service main()
```python
def main():
    port = 9105
    server_address = ('', port)
    
    # Run version checking in background thread on boot
    check_angati_version_async(AGENTS_ROOT)
    
    httpd = ThreadingHTTPServer(server_address, SRAHookHandler)
    print(f"[SRA Server] Running SRA Hybrid Hook Server on port {port}...", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("[SRA Server] Stopping server...", file=sys.stderr)
```

## 7. Integration & Mock Testing Design
To support Automated Testing (Milestone 3), we can design unit test scenarios in `nerves/workers/trading/test_angati_integration.py` to verify the warning behavior. Because standard execution does not have a real mismatch environment, we mock the path resolution and capture stderr.

```python
import io
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

class TestAngatiVersionChecking(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.local_exe = self.dir_path / "local_angati.exe"
        self.brain_exe = self.dir_path / "brain_angati.exe"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch('hook_service.resolve_local_angati_path')
    @patch('hook_service.resolve_brain_angati_path')
    def test_matching_version(self, mock_brain, mock_local):
        # Create identical mock files
        self.local_exe.write_bytes(b"version_1.0_binary")
        self.brain_exe.write_bytes(b"version_1.0_binary")
        mock_local.return_value = self.local_exe
        mock_brain.return_value = self.brain_exe

        captured_stderr = io.StringIO()
        with patch('sys.stderr', captured_stderr):
            # Run sync core checks directly
            hook_service.check_angati_version_sync(self.local_exe, self.brain_exe)
            
        self.assertEqual(captured_stderr.getvalue(), "")

    @patch('hook_service.resolve_local_angati_path')
    @patch('hook_service.resolve_brain_angati_path')
    def test_mismatched_version(self, mock_brain, mock_local):
        # Create different mock files
        self.local_exe.write_bytes(b"version_1.0_binary")
        self.brain_exe.write_bytes(b"version_2.0_binary")
        mock_local.return_value = self.local_exe
        mock_brain.return_value = self.brain_exe

        captured_stderr = io.StringIO()
        with patch('sys.stderr', captured_stderr):
            hook_service.check_angati_version_sync(self.local_exe, self.brain_exe)
            
        self.assertIn("WARNING: Local angati.exe version mismatch detected!", captured_stderr.getvalue())

    @patch('hook_service.resolve_local_angati_path')
    @patch('hook_service.resolve_brain_angati_path')
    def test_missing_files_silent(self, mock_brain, mock_local):
        # Local exe missing, brain exists
        self.brain_exe.write_bytes(b"version_2.0_binary")
        mock_local.return_value = self.local_exe  # Exe is missing
        mock_brain.return_value = self.brain_exe

        captured_stderr = io.StringIO()
        with patch('sys.stderr', captured_stderr):
            hook_service.check_angati_version_sync(self.local_exe, self.brain_exe)
            
        # Verify silent exit (no error printed)
        self.assertEqual(captured_stderr.getvalue(), "")
```
