#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════
# setup_git_hooks.sh — Cài đặt git hooks bảo mật
# Chạy 1 lần trên máy local sau khi clone repo
#
# Usage:
#   bash deploy/setup_git_hooks.sh
# ════════════════════════════════════════════════════════════════

set -euo pipefail
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOKS_SRC="${REPO_ROOT}/deploy/git-hooks"
HOOKS_DEST="${REPO_ROOT}/.git/hooks"

echo "Installing git hooks..."

# pre-commit: Secret leak scanner
cp "${HOOKS_SRC}/pre-commit" "${HOOKS_DEST}/pre-commit"
chmod +x "${HOOKS_DEST}/pre-commit"
log "pre-commit: Secret leak scanner installed"

# Cấu hình git để dùng hook directory tập trung (Git 2.9+)
git config core.hooksPath .git/hooks
log "git config: hooksPath = .git/hooks"

# Verify
log "Hooks installed:"
ls -la "${HOOKS_DEST}/" | grep -v "^total" | grep -v "^d" | while read -r line; do
    echo "  $line"
done

echo ""
log "Secret protection active ✅"
warn "Test: echo 'sk-ant-api03-fake' > /tmp/test.py; git add /tmp/test.py; git commit -m 'test'"
warn "Bypass (dangerous): git commit --no-verify -m 'message'"
