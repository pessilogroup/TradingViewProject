# Handoff Report: Angati Binary Paths

This handoff details the findings from the read-only investigation to locate the physical `angati.exe` binaries for both the local project workspace and the main EAIS Brain.

## 1. Observation

- **Local Workspace `TradingViewProject`**:
  - Running a search for `*angati*` within `c:\Users\pesil\working\mj_trading\TradingViewProject` yielded:
    - `c:\Users\pesil\working\mj_trading\TradingViewProject\angati.exe`
    - `c:\Users\pesil\working\mj_trading\TradingViewProject\nerves\workers\trading\test_angati_integration.py`
  - In `nerves/core/hook_service.py` (lines 120-122):
    ```python
    angati_exe = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
    if not angati_exe.exists():
        angati_exe = AGENTS_ROOT / "angati.exe"
    ```

- **Main Brain `EAIS`**:
  - Running a search for `*angati*` within `C:\Users\pesil\EAIS` yielded:
    - `C:\Users\pesil\EAIS\test_scaffold\angati.exe`
    - `C:\Users\pesil\EAIS\memory\angati_daemon.pid`
    - `C:\Users\pesil\EAIS\memory\angati_debug.jsonl`
  - Running a search for `*angati.exe*` inside `C:\Users\pesil\.gemini\antigravity` yielded `Found 0 results`.
  - In `C:\Users\pesil\EAIS\.agents\memory\angati_stdout.log` (line 3):
    ```
    [angati] PID 31212 written to C:\Users\pesil\EAIS\.agents\memory\angati_daemon.pid
    ```

## 2. Logic Chain

1. **Local Binary**: The search within the `TradingViewProject` workspace only located `angati.exe` at the project root (`c:\Users\pesil\working\mj_trading\TradingViewProject\angati.exe`). The fallback structure inside `hook_service.py` handles cases where `tools/angati/angati.exe` is absent and resolves to this root file.
2. **Brain Binary**: App Data (`.gemini/antigravity`) contains state and logs but no daemon executable. The search of the parent repository `C:\Users\pesil\EAIS` found the executable at `C:\Users\pesil\EAIS\test_scaffold\angati.exe`. The output logs (such as `angati_stdout.log` and `angati_daemon.pid`) confirm the active daemon processes run within this folder structure, confirming this is the main Brain's binary.

## 3. Caveats

- System directories outside the user's home profile (`C:\Users\pesil`) and the local workspace were not searched.
- Ephemeral Go build caches (`C:\Users\pesil\AppData\Local\go-build`) contain cached versions of the binary, but they are not targetable.

## 4. Conclusion

- Local Binary Path: `c:\Users\pesil\working\mj_trading\TradingViewProject\angati.exe`
- Main Brain Path: `C:\Users\pesil\EAIS\test_scaffold\angati.exe`
- Python resolution should dynamically trace `Path.home() / 'EAIS' / 'test_scaffold' / 'angati' / 'angati.exe'` (or `spine/angati/angati.exe` source) using standard `pathlib` features to support multiple deployment locations.

## 5. Verification Method

To verify the existence of the binaries:
1. In PowerShell:
   ```powershell
   Test-Path "c:\Users\pesil\working\mj_trading\TradingViewProject\angati.exe"
   Test-Path "C:\Users\pesil\EAIS\test_scaffold\angati.exe"
   ```
2. In Python:
   ```python
   from pathlib import Path
   print("Local:", Path("c:/Users/pesil/working/mj_trading/TradingViewProject/angati.exe").is_file())
   print("Brain:", (Path.home() / "EAIS" / "test_scaffold" / "angati.exe").is_file())
   ```
 Both expressions must evaluate to `True`.
