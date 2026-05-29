@echo off
echo ========================================
echo Running E2E (End-to-End) Tests
echo ========================================

pytest tests/e2e -v

if %errorlevel% neq 0 (
    echo [!] E2E Tests FAILED.
    exit /b %errorlevel%
) else (
    echo [OK] E2E Tests PASSED.
)
