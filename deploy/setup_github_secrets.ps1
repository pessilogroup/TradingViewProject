param(
    [switch]$DryRun = $false
)
$ErrorActionPreference = "Stop"

function Log     { Write-Host "[OK]  $args" -ForegroundColor Green }
function Warn    { Write-Host "[!!]  $args" -ForegroundColor Yellow }
function Err     { Write-Host "[ERR] $args" -ForegroundColor Red }
function Info    { Write-Host "[>>]  $args" -ForegroundColor Cyan }
function Section { Write-Host "`n=== $args ===" -ForegroundColor Cyan }

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  GitHub Secrets Setup - CI/CD Pipeline V2 Hardened  " -ForegroundColor Cyan
Write-Host "  Platform: Windows PowerShell                        " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

$RepoOrigin = git remote get-url origin 2>$null
if (-not $RepoOrigin) { Err "Cannot detect git remote origin."; exit 1 }
$Repo = $RepoOrigin -replace "git@github.com:", "" -replace "https://github.com/", "" -replace "\.git$", ""
Info "Repo: https://github.com/$Repo"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Err "GitHub CLI (gh) not installed. Run: winget install GitHub.cli"
    exit 1
}
gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Err "Not logged in. Run: gh auth login"
    exit 1
}
Log "GitHub CLI: $(gh --version | Select-Object -First 1)"

function Set-GhSecret {
    param([string]$Name, [string]$Value, [string]$Desc = "")
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -like "YOUR_*") {
        Warn "SKIP $Name -- not set ($Desc)"
        return
    }
    $Preview = $Value.Substring(0, [Math]::Min(4, $Value.Length)) + "****"
    if ($DryRun) {
        Write-Host "  [DRY] $Name = $Preview" -ForegroundColor Blue
        return
    }
    Write-Host "  Setting $Name ..." -NoNewline
    $Value | gh secret set $Name --repo $Repo --body -
    Write-Host " OK" -ForegroundColor Green
}

function Read-Input {
    param([string]$Prompt, [string]$Default = "")
    $v = Read-Host "  $Prompt"
    if ([string]::IsNullOrWhiteSpace($v)) { return $Default }
    return $v
}

function Read-Hidden {
    param([string]$Prompt)
    $s = Read-Host "  $Prompt" -AsSecureString
    $b = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { return [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($b) }
    finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

if ($DryRun) { Warn "DRY-RUN mode -- no secrets will be set" }

# === INPUT COLLECTION ===
Section "1. Server IPs (Tailscale)"
$ServerA = Read-Input "SERVER_A_IP  (Gateway, e.g. 100.x.x.1)" "100.x.x.1"
$ServerB = Read-Input "SERVER_B_IP  (Execution, e.g. 100.x.x.2)" "100.x.x.2"
$ServerC = Read-Input "SERVER_C_IP  (AI Core, e.g. 100.x.x.3)" "100.x.x.3"

Section "2. SSH Private Key"
$DefKey = "$env:USERPROFILE\.ssh\id_ed25519"
$KeyPath = Read-Input "Path to ED25519 private key" $DefKey
$SshKey = ""
if (Test-Path $KeyPath) {
    $SshKey = Get-Content $KeyPath -Raw
    Log "SSH key loaded from $KeyPath"
} else {
    Warn "Key not found: $KeyPath"
    Warn "Generate: ssh-keygen -t ed25519 -C tradingbot-ci -f $DefKey"
    Warn "Copy to servers via Git Bash:"
    Warn "  ssh-copy-id -i $DefKey.pub botuser@SERVER_A_IP"
    Warn "  ssh-copy-id -i $DefKey.pub botuser@SERVER_C_IP"
}

Section "3. Tailscale Ephemeral Auth Key"
Info "Get at: https://login.tailscale.com/admin/settings/keys"
Info "Settings: Ephemeral=ON, Reusable=ON, Tags=tag:ci"
$TsKey = Read-Hidden "TAILSCALE_AUTHKEY"

Section "4. Telegram"
$TgToken = Read-Hidden "TELEGRAM_BOT_TOKEN"
$TgChat  = Read-Input  "TELEGRAM_CHAT_ID"

Section "5. App Secrets"
$WH   = Read-Hidden "WEBHOOK_SECRET (TradingView to Server A)"
$VBS  = Read-Hidden "VPS_BUFFER_SECRET (Server A to Server C)"
$SB   = Read-Hidden "SERVER_B_SECRET (Server C to Server B)"

Section "6. AI API Keys"
$Anthropic = Read-Hidden "ANTHROPIC_API_KEY (sk-ant-...)"
$Gemini    = Read-Hidden "GEMINI_API_KEY"

Section "7. UptimeRobot (optional)"
Info "Get at: https://uptimerobot.com/dashboard (Main API Key)"
$UR = Read-Input "UPTIMEROBOT_API_KEY (Enter to skip)"

Section "8. Dashboard Token"
$AutoTok = -join (1..32 | ForEach-Object { [Convert]::ToString((Get-Random -Max 16), 16) })
$DashTok = Read-Input "DASHBOARD_TOKEN (Enter to auto-generate)"
if ([string]::IsNullOrWhiteSpace($DashTok)) { $DashTok = $AutoTok }

# === APPLY SECRETS ===
Section "Registering to $Repo"

Set-GhSecret "SERVER_A_IP"        $ServerA   "Tailscale IP Server A"
Set-GhSecret "SERVER_B_IP"        $ServerB   "Tailscale IP Server B"
Set-GhSecret "SERVER_C_IP"        $ServerC   "Tailscale IP Server C"
Set-GhSecret "SSH_PRIVATE_KEY"    $SshKey    "ED25519 private key"
Set-GhSecret "TAILSCALE_AUTHKEY"  $TsKey     "Tailscale ephemeral key"
Set-GhSecret "TELEGRAM_BOT_TOKEN" $TgToken   "Telegram bot token"
Set-GhSecret "TELEGRAM_CHAT_ID"   $TgChat    "Telegram chat ID"
Set-GhSecret "WEBHOOK_SECRET"     $WH        "TradingView webhook"
Set-GhSecret "VPS_BUFFER_SECRET"  $VBS       "VBS buffer secret"
Set-GhSecret "SERVER_B_SECRET"    $SB        "Server B execution"
Set-GhSecret "DASHBOARD_TOKEN"    $DashTok   "Dashboard bearer token"
Set-GhSecret "ANTHROPIC_API_KEY"  $Anthropic "Anthropic Claude"
Set-GhSecret "GEMINI_API_KEY"     $Gemini    "Google Gemini"
Set-GhSecret "UPTIMEROBOT_API_KEY" $UR       "UptimeRobot monitoring"

# === VERIFY ===
Section "Verification"
if (-not $DryRun) {
    Info "Registered secrets:"
    gh secret list --repo $Repo | ForEach-Object {
        $parts = $_ -split " "
        Write-Host "  [OK] $($parts[0])" -ForegroundColor Green
    }
}

# === SUMMARY ===
Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  DONE: GitHub Secrets Setup Complete                " -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Verify: https://github.com/$Repo/settings/secrets/actions"
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  [1] Copy SSH pubkey to servers (Git Bash):"
Write-Host "      ssh-copy-id -i $KeyPath.pub botuser@SERVER_A_IP"
Write-Host "      ssh-copy-id -i $KeyPath.pub botuser@SERVER_C_IP"
Write-Host ""
Write-Host "  [2] Tailscale ACL - add tag:ci at:"
Write-Host "      https://login.tailscale.com/admin/acls"
Write-Host ""
Write-Host "  [3] Test pipeline:"
Write-Host "      git commit --allow-empty -m `"test: trigger CI/CD`""
Write-Host "      git push origin main"
Write-Host "      https://github.com/$Repo/actions"
Write-Host ""
