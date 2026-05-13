#Requires -RunAsAdministrator
# Launch TradingView Desktop (MSIX/Microsoft Store version) with Chrome DevTools
# Protocol enabled on port 9222. Required for tradingview-mcp.

$ErrorActionPreference = "Stop"

$pkgName = "TradingView.Desktop"
$pkg = Get-AppxPackage -Name $pkgName -ErrorAction SilentlyContinue

if (-not $pkg) {
    Write-Host "ERROR: TradingView MSIX package '$pkgName' not installed." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Stopping any running TradingView instances..." -ForegroundColor Cyan
Get-Process TradingView -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Write-Host "Launching TradingView with --remote-debugging-port=9222..." -ForegroundColor Cyan
Write-Host "Package: $($pkg.PackageFamilyName)" -ForegroundColor DarkGray

# This call blocks until TradingView exits, so background it.
Start-Job -Name "TVLauncher" -ScriptBlock {
    param($pfn)
    Invoke-CommandInDesktopPackage `
        -PackageFamilyName $pfn `
        -AppId "TradingView.Desktop" `
        -Command "TradingView.exe" `
        -Args "--remote-debugging-port=9222" `
        -PreventBreakaway
} -ArgumentList $pkg.PackageFamilyName | Out-Null

Write-Host "Waiting for CDP port to open..." -ForegroundColor Cyan
$ok = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:9222/json/version" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "CDP up after $i seconds." -ForegroundColor Green
        Write-Host $r.Content -ForegroundColor DarkGray
        $ok = $true
        break
    } catch { }
}

if (-not $ok) {
    Write-Host "WARNING: CDP did not come up within 20s. TradingView may still be starting." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "TradingView is running with CDP on port 9222." -ForegroundColor Green
Write-Host "Keep this window open while using tradingview-mcp." -ForegroundColor Yellow
Write-Host "Closing this window will stop TradingView." -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop, or close this window."
# Keep the parent process alive so the background job (and TV) stays running
while ($true) {
    Start-Sleep -Seconds 30
    if (-not (Get-Process TradingView -ErrorAction SilentlyContinue)) {
        Write-Host "TradingView has exited." -ForegroundColor Yellow
        break
    }
}
