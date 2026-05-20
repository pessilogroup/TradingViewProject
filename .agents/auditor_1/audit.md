## Forensic Audit Report

**Work Product**: `nerves/core/hook_service.py` (version check implementation) and `nerves/workers/trading/test_angati_integration.py` (unit tests)
**Profile**: General Project
**Verdict**: CLEAN

### Phase Results
- **Hardcoded output detection**: PASS — Checked both files for hardcoded hashes, dummy bypasses, or fixed expected results. The implementation performs real SHA-256 computation, and tests dynamically generate temporary mismatch/matching files to verify the warning logic.
- **Facade detection**: PASS — The function `check_angati_version_async` contains real path resolution, existence checking, chunked binary read hashing, hash mismatch comparison, and async thread wrapping. It is a genuine implementation.
- **Pre-populated artifact detection**: PASS — No pre-populated log files, result files, or fake test run metadata are present in the workspace.
- **Test assertions check**: PASS — The assertions in `test_angati_integration.py` redirect `sys.stderr` to a `StringIO` stream, wait for the background thread to finish via `t.join()`, and verify the presence/absence of the mismatch warning string dynamically rather than relying on stubbed success boolean flags.
- **Dependency audit**: PASS — Core version check implementation relies entirely on Python standard library modules (`os`, `sys`, `time`, `hashlib`, `threading`, `tempfile`, `contextlib`, `io`, `unittest`, `pathlib`). No execution delegation to external tools or prohibited libraries exists.

---

### Evidence

#### 1. Implementation Code: `nerves/core/hook_service.py` (Lines 247-312)
```python
def check_angati_version_async():
    """Runs asynchronously in a daemon thread to check version compatibility of local and brain angati.exe."""
    def run_check():
        import os
        import hashlib
        
        # 1. Resolve local path
        local_path = None
        env_local = os.environ.get("ANGATI_LOCAL_EXE_PATH")
        if env_local:
            local_path = Path(env_local)
        else:
            cand1 = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
            cand2 = AGENTS_ROOT / "angati.exe"
            if cand1.exists():
                local_path = cand1
            else:
                local_path = cand2

        # 2. Resolve brain path
        brain_path = None
        env_brain = os.environ.get("ANGATI_BRAIN_EXE_PATH")
        if env_brain:
            brain_path = Path(env_brain)
        else:
            home = Path.home()
            candidates = [
                home / "EAIS" / "test_scaffold" / "angati.exe",
                home / "EAIS" / "spine" / "angati" / "angati.exe",
                home / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe",
            ]
            for cand in candidates:
                if cand.exists():
                    brain_path = cand
                    break
            if not brain_path:
                brain_path = candidates[-1]

        # 3. Check exists
        if not local_path.exists() or not brain_path.exists():
            return

        # 4. Compute hashes chunked
        def get_sha256(p):
            sha = hashlib.sha256()
            try:
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        sha.update(chunk)
                return sha.hexdigest()
            except Exception:
                return None

        local_hash = get_sha256(local_path)
        brain_hash = get_sha256(brain_path)

        if not local_hash or not brain_hash:
            return

        # 5. Warn on mismatch
        if local_hash != brain_hash:
            print("[SRA Server] WARNING: Local angati.exe version mismatch detected! Please manually restart the hook server to synchronize the binary.", file=sys.stderr)

    t = threading.Thread(target=run_check, daemon=True)
    t.start()
    return t
```

#### 2. Test Cases: `nerves/workers/trading/test_angati_integration.py` (Lines 121-237)
```python
    def test_angati_version_mismatch_warning(self):
        """Tests that a mismatch triggers the stderr warning (using environment overrides)."""
        import tempfile
        import os
        from contextlib import redirect_stderr
        from io import StringIO

        f1 = tempfile.NamedTemporaryFile(delete=False)
        f2 = tempfile.NamedTemporaryFile(delete=False)
        try:
            f1.write(b"local_version_data")
            f1.close()
            f2.write(b"brain_version_data")
            f2.close()

            os.environ["ANGATI_LOCAL_EXE_PATH"] = f1.name
            os.environ["ANGATI_BRAIN_EXE_PATH"] = f2.name

            f = StringIO()
            with redirect_stderr(f):
                t = hook_service.check_angati_version_async()
                if t:
                    t.join()
            
            output = f.getvalue()
            self.assertIn("WARNING: Local angati.exe version mismatch detected!", output)
        finally:
            os.environ.pop("ANGATI_LOCAL_EXE_PATH", None)
            os.environ.pop("ANGATI_BRAIN_EXE_PATH", None)
            for temp_f in (f1, f2):
                try:
                    if os.path.exists(temp_f.name):
                        os.unlink(temp_f.name)
                except Exception:
                    pass

    def test_angati_version_matching(self):
        """Tests that identical file hashes trigger no warning."""
        import tempfile
        import os
        from contextlib import redirect_stderr
        from io import StringIO

        f1 = tempfile.NamedTemporaryFile(delete=False)
        f2 = tempfile.NamedTemporaryFile(delete=False)
        try:
            content = b"matching_version_data"
            f1.write(content)
            f1.close()
            f2.write(content)
            f2.close()

            os.environ["ANGATI_LOCAL_EXE_PATH"] = f1.name
            os.environ["ANGATI_BRAIN_EXE_PATH"] = f2.name

            f = StringIO()
            with redirect_stderr(f):
                t = hook_service.check_angati_version_async()
                if t:
                    t.join()
            
            output = f.getvalue()
            self.assertNotIn("WARNING: Local angati.exe version mismatch detected!", output)
        finally:
            os.environ.pop("ANGATI_LOCAL_EXE_PATH", None)
            os.environ.pop("ANGATI_BRAIN_EXE_PATH", None)
            for temp_f in (f1, f2):
                try:
                    if os.path.exists(temp_f.name):
                        os.unlink(temp_f.name)
                except Exception:
                    pass

    def test_angati_version_missing_files(self):
        """Tests that missing file conditions are handled gracefully and silently."""
        import tempfile
        import os
        from contextlib import redirect_stderr
        from io import StringIO

        # Both missing
        os.environ["ANGATI_LOCAL_EXE_PATH"] = "non_existent_file_local.exe"
        os.environ["ANGATI_BRAIN_EXE_PATH"] = "non_existent_file_brain.exe"
        try:
            f = StringIO()
            with redirect_stderr(f):
                t = hook_service.check_angati_version_async()
                if t:
                    t.join()
            self.assertEqual(f.getvalue(), "")
        finally:
            os.environ.pop("ANGATI_LOCAL_EXE_PATH", None)
            os.environ.pop("ANGATI_BRAIN_EXE_PATH", None)

        # One missing, one exists
        f1 = tempfile.NamedTemporaryFile(delete=False)
        try:
            f1.write(b"local_version_data")
            f1.close()
            os.environ["ANGATI_LOCAL_EXE_PATH"] = f1.name
            os.environ["ANGATI_BRAIN_EXE_PATH"] = "non_existent_file_brain.exe"
            
            f = StringIO()
            with redirect_stderr(f):
                t = hook_service.check_angati_version_async()
                if t:
                    t.join()
            self.assertEqual(f.getvalue(), "")
        finally:
            os.environ.pop("ANGATI_LOCAL_EXE_PATH", None)
            os.environ.pop("ANGATI_BRAIN_EXE_PATH", None)
            try:
                if os.path.exists(f1.name):
                    os.unlink(f1.name)
            except Exception:
                pass
```
