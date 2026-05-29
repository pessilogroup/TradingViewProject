# ════════════════════════════════════════════════════════════════════════════
# setup_github_secrets.ps1 — Đăng ký GitHub Secrets cho CI/CD
# Chạy trên máy LOCAL Windows (PowerShell 5.1+ hoặc PowerShell 7+)
#
# Prerequisites:
#   1. GitHub CLI: winget install GitHub.cli
#   2. Đăng nhập:  gh auth login
#   3. Git for Windows (đã có khi dùng VS Code/Git)
#
# Usage:
#   .\deploy\setup_github_secrets.ps1
#   # Dry-run (xem secrets sẽ được set mà không apply):
#   .\deploy\setup_github_secrets.ps1 -DryRun
# ════════════════════════════════════════════════════════════════════════════
param(
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

# ── Colors ────────────────────────────────────────────────────────────────
function Log   { Write-Host "[OK] $args" -ForegroundColor Green }
function Warn  { Write-Host "[!]  $args" -ForegroundColor Yellow }
function Err   { Write-Host "[X]  $args" -ForegroundColor Red }
function Info  { Write-Host "[->] $args" -ForegroundColor Cyan }
function Section { Write-Host "`n══ $args ══" -ForegroundColor Cyan }

Write-Host @"

  ╔═══════════════════════════════════════════════════════╗
  ║  🔐 GitHub Secrets Setup — CI/CD Pipeline V2 Hardened ║
  ║  Platform: Windows PowerShell                         ║
  ╚═══════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# ── Detect repo ────────────────────────────────────────────────────────────
$RepoOrigin = git remote get-url origin 2>$null
if (-not $RepoOrigin) { Err "Cannot detect git remote origin."; exit 1 }
$Repo = $RepoOrigin -replace "git@github.com:", "" -replace "https://github.com/", "" -replace "\.git$", ""
Info "Repo: https://github.com/$Repo"

# ── Check gh CLI ───────────────────────────────────────────────────────────
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Err "GitHub CLI (gh) not installed."
    Err "Install: winget install GitHub.cli"
    Err "Then:    gh auth login"
    exit 1
}

$GhStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Err "Not logged in. Run: gh auth login"
    exit 1
}
Log "GitHub CLI OK: $(gh --version | Select-Object -First 1)"

# ── Helper: set one secret ─────────────────────────────────────────────────
function Set-GhSecret {
    param(
        [string]$Name,
        [string]$Value,
        [string]$Description = ""
    )
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -like "YOUR_*" -or $Value -like "*PLACEHOLDER*") {
        Warn "SKIP $Name — value not set ($Description)"
        return
    }
    if ($DryRun) {
        Write-Host "  [DRY-RUN] Would set: $Name = $($Value.Substring(0, [Math]::Min(4, $Value.Length)))****" -ForegroundColor Blue
        return
    }
    Write-Host "  Setting $Name..." -NoNewline
    $Value | gh secret set $Name --repo $Repo --body -
    Write-Host " ✓" -ForegroundColor Green
}

# ── Read sensitive input (hidden) ──────────────────────────────────────────
function Read-SecureInput {
    param([string]$Prompt, [string]$Default = "")
    $input = Read-Host "  $Prompt"
    if ([string]::IsNullOrWhiteSpace($input)) { return $Default }
    return $input
}

function Read-HiddenInput {
    param([string]$Prompt)
    $secure = Read-Host "  $Prompt" -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) }
    finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

if ($DryRun) { Warn "DRY-RUN mode — no secrets will actually be set" }

# ════════════════════════════════════════════════════════════════════════════
# INPUT COLLECTION
# ════════════════════════════════════════════════════════════════════════════

Section "1. Server IPs (Tailscale 100.x.x.x)"
$ServerAIp = Read-SecureInput "SERVER_A_IP (Tailscale IP Server A Gateway)" "100.x.x.1"
$ServerBIp = Read-SecureInput "SERVER_B_IP (Tailscale IP Server B Execution)" "100.x.x.2"
$ServerCIp = Read-SecureInput "SERVER_C_IP (Tailscale IP Server C AI Core)" "100.x.x.3"

Section "2. SSH Private Key"
$DefaultKeyPath = "$env:USERPROFILE\.ssh\id_ed25519"
$SshKeyPath = Read-SecureInput "Path to ED25519 private key" $DefaultKeyPath

$SshPrivateKey = ""
if (Test-Path $SshKeyPath) {
    $SshPrivateKey = Get-Content $SshKeyPath -Raw
    Log "SSH key loaded: $SshKeyPath"
} else {
    Warn "Key not found: $SshKeyPath"
    Warn "Create new key:"
    Warn "  ssh-keygen -t ed25519 -C 'tradingbot-ci-cd' -f $DefaultKeyPath"
    Warn "Then copy to servers:"
    Warn "  type $DefaultKeyPath.pub | ssh botuser@SERVER_A_IP 'cat >> ~/.ssh/authorized_keys'"
    Warn "  type $DefaultKeyPath.pub | ssh botuser@SERVER_C_IP 'cat >> ~/.ssh/authorized_keys'"
}

Section "3. Tailscale Ephemeral Auth Key"
Info "Get at: https://login.tailscale.com/admin/settings/keys"
Info "Settings: Ephemeral=ON, Reusable=ON, Tags=tag:ci"
$TailscaleAuthkey = Read-HiddenInput "TAILSCALE_AUTHKEY"

Section "4. Telegram (Alert notifications)"
$TelegramToken = Read-HiddenInput "TELEGRAM_BOT_TOKEN"
$TelegramChatId = Read-SecureInput "TELEGRAM_CHAT_ID"

Section "5. TradingBot Application Secrets"
$WebhookSecret    = Read-HiddenInput "WEBHOOK_SECRET (TradingView → Server A)"
$VpsBufferSecret  = Read-HiddenInput "VPS_BUFFER_SECRET (Server A → Server C)"
$ServerBSecret    = Read-HiddenInput "SERVER_B_SECRET (Server C → Server B)"

Section "6. AI Provider API Keys"
$AnthropicKey = Read-HiddenInput "ANTHROPIC_API_KEY (sk-ant-...)"
$GeminiKey    = Read-HiddenInput "GEMINI_API_KEY"

Section "7. UptimeRobot (optional)"
Info "Get at: https://uptimerobot.com/dashboard#api → Main API Key"
$UptimeRobotKey = Read-SecureInput "UPTIMEROBOT_API_KEY (press Enter to skip)"

Section "8. Dashboard Auth Token"
$AutoToken = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
$DashToken = Read-SecureInput "DASHBOARD_TOKEN (Enter to auto-generate: $($AutoToken.Substring(0,8))****)"
if ([string]::IsNullOrWhiteSpace($DashToken)) { $DashToken = $AutoToken }

# ════════════════════════════════════════════════════════════════════════════
# APPLY SECRETS
# ════════════════════════════════════════════════════════════════════════════

Section "Registering secrets → $Repo"

# Infrastructure
Set-GhSecret "SERVER_A_IP"       $ServerAIp       "Tailscale IP Server A"
Set-GhSecret "SERVER_B_IP"       $ServerBIp       "Tailscale IP Server B"
Set-GhSecret "SERVER_C_IP"       $ServerCIp       "Tailscale IP Server C"
Set-GhSecret "SSH_PRIVATE_KEY"   $SshPrivateKey   "ED25519 private key"
Set-GhSecret "TAILSCALE_AUTHKEY" $TailscaleAuthkey "Tailscale ephemeral key"

# Notifications
Set-GhSecret "TELEGRAM_BOT_TOKEN" $TelegramToken  "Telegram bot token"
Set-GhSecret "TELEGRAM_CHAT_ID"   $TelegramChatId "Telegram chat ID"

# Application
Set-GhSecret "WEBHOOK_SECRET"     $WebhookSecret   "TradingView webhook"
Set-GhSecret "VPS_BUFFER_SECRET"  $VpsBufferSecret "VBS buffer secret"
Set-GhSecret "SERVER_B_SECRET"    $ServerBSecret   "Server B execution"
Set-GhSecret "DASHBOARD_TOKEN"    $DashToken       "Dashboard bearer token"

# AI
Set-GhSecret "ANTHROPIC_API_KEY"  $AnthropicKey    "Anthropic Claude"
Set-GhSecret "GEMINI_API_KEY"     $GeminiKey       "Google Gemini"

# Monitoring
Set-GhSecret "UPTIMEROBOT_API_KEY" $UptimeRobotKey "UptimeRobot monitoring"

# ════════════════════════════════════════════════════════════════════════════
# VERIFY
# ════════════════════════════════════════════════════════════════════════════

Section "Verification"

if (-not $DryRun) {
    Info "Registered secrets:"
    gh secret list --repo $Repo | ForEach-Object {
        $SecretName = ($_ -split '\s+')[0]
        Write-Host "  [OK] $SecretName" -ForegroundColor Green
    }
}

Write-Host @"

  ╔══════════════════════════════════════════════════════╗
  ║  ✅ GitHub Secrets Setup Complete                    ║
  ╚══════════════════════════════════════════════════════╝

  Verify: https://github.com/$Repo/settings/secrets/actions

  ⚠️  Còn cần làm thủ công:

  [1] Copy SSH public key lên servers (từ PowerShell):
      type $SshKeyPath.pub | ssh botuser@`$SERVER_A_IP 'mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys'
      type $SshKeyPath.pub | ssh botuser@`$SERVER_C_IP 'mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys'

  [2] Tailscale ACL — thêm tag:ci vào:
      https://login.tailscale.com/admin/acls
      {"action": "accept", "src": ["tag:ci"], "dst": ["*:22"]}

  [3] Test CI/CD:
      git commit --allow-empty -m 'test: trigger CI/CD'
      git push origin main
      # Xem: https://github.com/$Repo/actions

"@ -ForegroundColor Cyan
