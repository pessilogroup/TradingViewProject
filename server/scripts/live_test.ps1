$ErrorActionPreference = "Stop"
$serverUrl = "http://localhost:5000/webhook"
$payloadPath = Join-Path $PSScriptRoot "..\tests\mock_data\payloads.json"

if (-not (Test-Path $payloadPath)) {
    Write-Host "[-] Missing payloads.json"
    exit 1
}

$payloads = Get-Content $payloadPath | ConvertFrom-Json

function Test-Webhook {
    param (
        [string]$TestName,
        [object]$Payload,
        [int]$ExpectedStatusCode,
        [string]$ExpectedStatus,
        [string]$ExpectedReason
    )
    
    Write-Host "`n>>> Running: $TestName" -ForegroundColor Cyan
    
    try {
        $jsonPayload = $Payload | ConvertTo-Json -Depth 10 -Compress
        $response = Invoke-RestMethod -Uri $serverUrl -Method Post -Body $jsonPayload -ContentType "application/json"
        
        if ($ExpectedStatusCode -eq 200) {
            if ($response.received -ne $true) {
                Write-Host "[-] FAILED: Response 'received' is not true" -ForegroundColor Red
                return $false
            }
            if ($ExpectedStatus -and $response.status -ne $ExpectedStatus) {
                Write-Host "[-] FAILED: Expected status '$ExpectedStatus', got '$($response.status)'" -ForegroundColor Red
                return $false
            }
            if ($ExpectedReason -and $response.reason -ne $ExpectedReason) {
                Write-Host "[-] FAILED: Expected reason '$ExpectedReason', got '$($response.reason)'" -ForegroundColor Red
                return $false
            }
            Write-Host "[+] PASSED" -ForegroundColor Green
            return $true
        } else {
            Write-Host "[-] FAILED: Expected HTTP $ExpectedStatusCode but request succeeded (HTTP 200)" -ForegroundColor Red
            return $false
        }
    } catch {
        if ($_.Exception.Response.StatusCode) {
            $errCode = [int]$_.Exception.Response.StatusCode
            if ($errCode -eq $ExpectedStatusCode) {
                Write-Host "[+] PASSED (Got expected error code $errCode)" -ForegroundColor Green
                return $true
            } else {
                Write-Host "[-] FAILED: Expected HTTP $ExpectedStatusCode, got HTTP $errCode" -ForegroundColor Red
                return $false
            }
        }
        Write-Host "[-] FAILED: $_" -ForegroundColor Red
        return $false
    }
}

$success = 0
$total = 0

# 1. Valid 1H Buy
$total++
if (Test-Webhook -TestName "Valid 1H Buy" -Payload $payloads.valid_1h_buy -ExpectedStatusCode 200 -ExpectedStatus "processing_async") { $success++ }

# 2. Invalid 4H Buy (Circuit Breaker)
$total++
if (Test-Webhook -TestName "Invalid 4H Buy" -Payload $payloads.invalid_4h_buy -ExpectedStatusCode 200 -ExpectedStatus "rejected" -ExpectedReason "invalid_timeframe") { $success++ }

# 3. Invalid Secret
$total++
if (Test-Webhook -TestName "Invalid Secret" -Payload $payloads.invalid_secret -ExpectedStatusCode 401) { $success++ }

# 4. Missing Interval (Circuit Breaker)
$total++
if (Test-Webhook -TestName "Missing Interval" -Payload $payloads.missing_interval -ExpectedStatusCode 200 -ExpectedStatus "rejected" -ExpectedReason "invalid_timeframe") { $success++ }

# 5. Missing QuoteQty (Fallback size=10)
$total++
$missingQty = $payloads.valid_1h_buy.PSObject.Copy()
$missingQty.psobject.properties.remove("quoteQty")
if (Test-Webhook -TestName "Missing QuoteQty (Fallback)" -Payload $missingQty -ExpectedStatusCode 200 -ExpectedStatus "processing_async") { $success++ }

# 6. Invalid Price Type
$total++
$invalidPrice = $payloads.valid_1h_buy.PSObject.Copy()
$invalidPrice.price = "NotANumber"
if (Test-Webhook -TestName "Invalid Price Type" -Payload $invalidPrice -ExpectedStatusCode 200 -ExpectedStatus "processing_async") { $success++ }

# 7. Unknown Action
$total++
$unknownAction = $payloads.valid_1h_buy.PSObject.Copy()
$unknownAction.action = "hold"
if (Test-Webhook -TestName "Unknown Action" -Payload $unknownAction -ExpectedStatusCode 200) { $success++ }

# 8. Load Test
Write-Host "`n>>> Running: Load Test (5 rapid requests)" -ForegroundColor Cyan
$loadSuccess = $true
for ($i = 1; $i -le 5; $i++) {
    $json = $payloads.valid_1h_buy | ConvertTo-Json -Compress
    $res = Invoke-RestMethod -Uri $serverUrl -Method Post -Body $json -ContentType "application/json"
    if ($res.status -ne "processing_async") {
        $loadSuccess = $false
    }
}
$total++
if ($loadSuccess) {
    Write-Host "[+] PASSED" -ForegroundColor Green
    $success++
} else {
    Write-Host "[-] FAILED" -ForegroundColor Red
}

Write-Host "`n========================================"
Write-Host "Test Results: $success / $total Passed"
if ($success -eq $total) {
    exit 0
} else {
    exit 1
}
