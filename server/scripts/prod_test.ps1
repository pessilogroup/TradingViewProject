$serverUrl = "http://localhost:5000/webhook?secret=your_super_secret_key"
$payload = @{
    action = "buy"
    symbol = "BINANCE:BTCUSDT"
    price = 65000.00
    interval = "1h"
}
$jsonPayload = $payload | ConvertTo-Json -Compress
Write-Host ">>> Sending Production Live Test Payload..." -ForegroundColor Cyan
$response = Invoke-RestMethod -Uri $serverUrl -Method Post -Body $jsonPayload -ContentType "application/json"
Write-Host "Response: "
$response | Format-List
