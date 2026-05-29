# TradingView Desktop CDP Discovery & Integration Analysis

## Executive Summary
This analysis details how to detect, locate, and launch **TradingView Desktop** on Windows with Chrome DevTools Protocol (CDP) enabled on port `9222`. 

Our findings indicate:
1. **MSIX App Store Version** is the exclusive installation type on this system. Direct execution of the binary from `C:\Program Files\WindowsApps\...` using the resolved path from `Get-AppxPackage` succeeds **without administrator elevation**, bypassing the need for `Invoke-CommandInDesktopPackage`.
2. **Standard installation paths** (under `Local AppData` or `Program Files`) do not exist on this environment but are documented for completeness.
3. The health check mechanism of the Node-based `tradingview-mcp` connects to `http://localhost:9222/json/list` and filters for targets referencing `tradingview.com/chart` to establish a CDP session.

---

## 1. Path Analysis for TradingView Desktop on Windows
TradingView Desktop can be installed via two primary methods on Windows: standard desktop installers or the MSIX/Microsoft Store package.

### Standard Desktop Installation Paths
When installed using a traditional `.exe` or `.msi` installer, TradingView places its executable in one of the following directories:
* **User-local Install:**
  * `%LOCALAPPDATA%\Programs\TradingView\TradingView.exe`
  * `%LOCALAPPDATA%\TradingView\TradingView.exe`
* **System-wide (All Users) Install:**
  * `%PROGRAMFILES%\TradingView\TradingView.exe` (64-bit)
  * `%PROGRAMFILES(X86)%\TradingView\TradingView.exe` (32-bit)

### MSIX / Microsoft Store Installation Path
When installed from the Microsoft Store, TradingView is deployed as a packaged app:
* **Package Name:** `TradingView.Desktop`
* **Publisher ID:** `n534cwy3pjxzj` (Package Family Name: `TradingView.Desktop_n534cwy3pjxzj`)
* **Installation Directory:** `C:\Program Files\WindowsApps\TradingView.Desktop_<Version>_<Architecture>__n534cwy3pjxzj`

#### Dynamic Resolution via PowerShell
Since the version number in the MSIX path changes dynamically, the path must be resolved at runtime using the `Get-AppxPackage` cmdlet:
```powershell
(Get-AppxPackage -Name "TradingView.Desktop").InstallLocation
```
Adding `\TradingView.exe` to this directory gives the absolute path to the executable:
`C:\Program Files\WindowsApps\TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj\TradingView.exe`

---

## 2. Examination of nerves MCP Client Health Check
The connection health check is defined in `nerves/workers/trading/mcp_client.py` and delegates to the Node.js CLI tool:

### Health Check Sequence
1. **Command Execution:** The Python wrapper invokes `node tradingview-mcp/src/cli/index.js status --json`.
2. **CLI Router Delegation:** The CLI router delegates to `core.healthCheck()` in `tradingview-mcp/src/core/health.js`.
3. **CDP Target Query:** The JavaScript core requests `http://localhost:9222/json/list` to find target pages.
4. **Target Selection:** It searches for target pages matching `tradingview.com/chart` (or fallback `tradingview`).
5. **WebSocket Verification:** It establishes a WebSocket session to the selected page's debugger URL, and executes a runtime script to check if `window.TradingViewApi` is loaded and active.
6. **JSON Response:** The CLI outputs JSON including `cdp_connected: true` and the active symbol.

---

## 3. Auto-Detection and Launch Logic
To automate this, we formulate a Python implementation that detects, resolves, and launches the app with `--remote-debugging-port=9222`.

### Python Implementation (`tv_launcher.py` sketch)
```python
import os
import subprocess
import time
import urllib.request
import json

CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}/json/version"

def is_cdp_responding() -> bool:
    """Check if the CDP port is open and responding to version queries."""
    try:
        with urllib.request.urlopen(CDP_URL, timeout=1.5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return "webSocketDebuggerUrl" in data
    except Exception:
        pass
    return False

def is_process_running(process_name="TradingView.exe") -> bool:
    """Check if the TradingView process is active in the task list."""
    try:
        cmd = f'tasklist /FI "IMAGENAME eq {process_name}" /FO CSV'
        output = subprocess.check_output(cmd, shell=True, text=True)
        return process_name.lower() in output.lower()
    except Exception:
        return False

def kill_tradingview():
    """Kill any running TradingView instances to clear the path for CDP relaunch."""
    try:
        subprocess.run("taskkill /F /IM TradingView.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
    except Exception:
        pass

def resolve_tv_executable() -> str:
    """Resolve the path to the TradingView executable (both Standard and MSIX)."""
    # 1. Standard Paths
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", "")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")
    
    candidates = [
        os.path.join(local_app_data, "Programs", "TradingView", "TradingView.exe"),
        os.path.join(local_app_data, "TradingView", "TradingView.exe"),
        os.path.join(program_files, "TradingView", "TradingView.exe"),
        os.path.join(program_files_x86, "TradingView", "TradingView.exe")
    ]
    
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    # 2. MSIX Package Path Resolution (via PowerShell)
    try:
        ps_cmd = "powershell -Command \"(Get-AppxPackage -Name 'TradingView.Desktop').InstallLocation\""
        result = subprocess.run(ps_cmd, capture_output=True, text=True, shell=True)
        install_dir = result.stdout.strip()
        if install_dir:
            msix_exe = os.path.join(install_dir, "TradingView.exe")
            if os.path.exists(msix_exe):
                return msix_exe
    except Exception:
        pass
        
    return ""

def launch_and_connect(timeout_sec=15) -> bool:
    """Locate, launch with CDP, and wait for connection."""
    # Step A: Check if already running and responding
    if is_cdp_responding():
        print("[+] TradingView is already running and connected to CDP.")
        return True
        
    # Step B: If running but CDP is unresponsive, we must restart it
    if is_process_running():
        print("[-] TradingView is running but CDP is unresponsive. Restarting...")
        kill_tradingview()
        
    # Step C: Locate the binary
    exe_path = resolve_tv_executable()
    if not exe_path:
        print("[!] Error: Could not locate TradingView Desktop binary.")
        return False
        
    print(f"[+] Found TradingView binary at: {exe_path}")
    print(f"[+] Launching with --remote-debugging-port={CDP_PORT}...")
    
    # Step D: Launch process in background (detached to prevent blocking)
    try:
        # DETACHED_PROCESS flag prevents the spawned process from inheriting terminal session
        subprocess.Popen(
            [exe_path, f"--remote-debugging-port={CDP_PORT}"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    except Exception as e:
        print(f"[!] Failed to launch process: {e}")
        return False
        
    # Step E: Poll CDP endpoint
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if is_cdp_responding():
            print(f"[+] Successfully connected to TradingView CDP on port {CDP_PORT}!")
            return True
        time.sleep(1.0)
        
    print("[!] Timeout: TradingView launched but CDP did not respond within limit.")
    return False
```

---

## 4. Verified Commands for Verification & Diagnostics

### Retrieve MSIX Package Info
```powershell
Get-AppxPackage -Name "TradingView.Desktop"
```

### Retrieve Installation Directory directly
```powershell
(Get-AppxPackage -Name "TradingView.Desktop").InstallLocation
```

### Kill Running Instances
```powershell
taskkill /F /IM TradingView.exe
```

### Direct launch without elevation (MSIX Executable)
```powershell
Start-Process "C:\Program Files\WindowsApps\TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj\TradingView.exe" -ArgumentList "--remote-debugging-port=9222"
```

### Verify CDP Port Status
```powershell
Invoke-RestMethod -Uri "http://localhost:9222/json/version"
```
