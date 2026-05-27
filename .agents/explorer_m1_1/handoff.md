# Handoff Report — TV CDP Discovery

## 1. Observation
We observed the following files and command outputs:
1. **MSIX Launcher Script (`scripts/launch_tv_msix_cdp.ps1`)**:
   - Uses `Get-AppxPackage -Name "TradingView.Desktop"` to query installer info.
   - Launches via `Invoke-CommandInDesktopPackage` (which has a comment `#Requires -RunAsAdministrator`).
2. **MCP Client Wrapper (`nerves/workers/trading/mcp_client.py`)**:
   - The health check runs: `result = await self._run("status", timeout=5)` (Line 104).
3. **Core Health Modules (`tradingview-mcp/src/core/health.js` and `connection.js`)**:
   - Win32 paths candidates array (Line 172-176):
     ```javascript
     win32: [
       `${process.env.LOCALAPPDATA}\\TradingView\\TradingView.exe`,
       `${process.env.PROGRAMFILES}\\TradingView\\TradingView.exe`,
       `${process.env['PROGRAMFILES(X86)']}\\TradingView\\TradingView.exe`,
     ]
     ```
   - CDP Port hardcoding (Line 6 in `connection.js`):
     ```javascript
     const CDP_PORT = 9222;
     ```
4. **AppxPackage Verification Output**:
   Running `Get-AppxPackage -Name *TradingView*` returned:
   ```
   Name              : TradingView.Desktop
   Version           : 3.1.0.7818
   InstallLocation   : C:\Program Files\WindowsApps\TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj
   PackageFamilyName : TradingView.Desktop_n534cwy3pjxzj
   ```
5. **Direct Run without Admin Privileges**:
   - Executing `Start-Process 'C:\Program Files\WindowsApps\TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj\TradingView.exe' -ArgumentList '--remote-debugging-port=9222'` succeeded immediately without triggering UAC prompt.
   - Process list successfully showed multiple `TradingView` processes.
   - `Invoke-RestMethod -Uri 'http://localhost:9222/json/version'` successfully returned:
     ```
     Browser  : Chrome/120.0.6099.291
     Protocol-Version : 1.3
     User-Agent : Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) TradingView/3.1.0 Chrome/120.0.6099.291 Electron/28.2.1 Safari/537.36
     ```

## 2. Logic Chain
- **Step 1**: The user's system only has the MSIX store version installed, as proved by `Get-AppxPackage` returning details while standard directories (`AppData` and `Program Files`) returned `False` during path existence tests.
- **Step 2**: The standard `scripts/launch_tv_msix_cdp.ps1` script relies on `Invoke-CommandInDesktopPackage` which traditionally requires administrator rights.
- **Step 3**: By extracting `InstallLocation` dynamically, we can run the target `TradingView.exe` directly under the WindowsApps package folder. This action succeeded as a normal user.
- **Step 4**: Querying `http://localhost:9222/json/version` confirms that launching the MSIX binary directly with the flag `--remote-debugging-port=9222` successfully enables the CDP server on port 9222.
- **Step 5**: To automate this in Python or PowerShell, we check for a listening socket on port `9222` using `http://localhost:9222/json/version`, locate the binary dynamically via standard candidates and `Get-AppxPackage`, kill stale processes if CDP is down, and launch in a detached state.

## 3. Caveats
- Direct execution from `C:\Program Files\WindowsApps` works for Centennial-style MSIX apps (like TradingView Desktop, which is an Electron app wrapped in an MSIX container). This may not work for native UWP apps, but it is valid for TradingView.
- The version string in `TradingView.Desktop_3.1.0.7818_x64__n534cwy3pjxzj` changes whenever the Microsoft Store updates the app. Therefore, we must dynamically lookup `InstallLocation` using PowerShell at runtime rather than hardcoding the folder path.

## 4. Conclusion
We successfully mapped the standard installation locations, analyzed the health-check connection protocol (which queries `/json/list` and `/json/version` on port 9222), and verified that a normal user can bypass the administrative requirement of `Invoke-CommandInDesktopPackage` by launching the wrapped binary inside the MSIX `InstallLocation` directly with `--remote-debugging-port=9222`.

## 5. Verification Method
1. Ensure TradingView Desktop is closed.
2. In PowerShell, execute:
   ```powershell
   $path = (Get-AppxPackage -Name "TradingView.Desktop").InstallLocation
   Start-Process "$path\TradingView.exe" -ArgumentList "--remote-debugging-port=9222"
   ```
3. Test that the port has opened:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:9222/json/version"
   ```
4. Verify the response contains the `webSocketDebuggerUrl` field and `TradingView` User-Agent.
