# ════════════════════════════════════════════════════════════════
# setup_git_hooks.ps1 — Cài đặt git hooks bảo mật (Windows)
# Chạy 1 lần sau khi clone repo
#
# Usage:
#   .\deploy\setup_git_hooks.ps1
# ════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

function Log  { Write-Host "[OK] $args" -ForegroundColor Green }
function Warn { Write-Host "[!]  $args" -ForegroundColor Yellow }
function Info { Write-Host "[->] $args" -ForegroundColor Cyan }

# ── Detect repo root ────────────────────────────────────────────────────────
$RepoRoot = git rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
    Write-Host "[X] Not inside a git repo" -ForegroundColor Red
    exit 1
}
$RepoRoot = $RepoRoot -replace '/', '\'

$HooksSrc  = Join-Path $RepoRoot "deploy\git-hooks"
$HooksDest = Join-Path $RepoRoot ".git\hooks"

Write-Host @"

  ╔═══════════════════════════════════════════╗
  ║  🔒 Git Hooks Setup — Secret Protection  ║
  ╚═══════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# ── pre-commit hook (Secret Scanner) ───────────────────────────────────────
# Git for Windows chạy hooks qua Git Bash (sh/bash) — file bash hoạt động
$PreCommitSrc  = Join-Path $HooksSrc  "pre-commit"
$PreCommitDest = Join-Path $HooksDest "pre-commit"

if (Test-Path $PreCommitSrc) {
    # Đảm bảo thư mục hooks tồn tại
    New-Item -ItemType Directory -Force -Path $HooksDest | Out-Null

    Copy-Item -Path $PreCommitSrc -Destination $PreCommitDest -Force

    # Git for Windows cần file không có BOM và dùng LF line endings
    $content = Get-Content $PreCommitDest -Raw
    $content = $content -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($PreCommitDest, $content, [System.Text.UTF8Encoding]::new($false))

    Log "pre-commit hook installed: $PreCommitDest"
    Log "  → Scans: Anthropic, Gemini, Tailscale, Telegram, SSH keys, hex tokens"
} else {
    Warn "pre-commit hook source not found: $PreCommitSrc"
}

# ── Git config: dùng hook path ─────────────────────────────────────────────
git config core.hooksPath .git/hooks
Log "git config: core.hooksPath = .git/hooks"

# ── Verify ──────────────────────────────────────────────────────────────────
Write-Host ""
Log "Hooks installed:"
Get-ChildItem $HooksDest -File | ForEach-Object {
    Write-Host "  $($_.Name)  ($($_.Length) bytes)" -ForegroundColor Cyan
}

Write-Host @"

  ✅ Secret protection active!

  Test hook (phải bị BLOCK):
    'sk-ant-api03-fakekeyhere' | Out-File test_secret.tmp
    git add test_secret.tmp
    git commit -m 'should be blocked'
    Remove-Item test_secret.tmp; git restore --staged test_secret.tmp 2>>`$null

  Bypass (dùng khi biết chắc không leak):
    git commit --no-verify -m 'your message'

"@ -ForegroundColor Green
