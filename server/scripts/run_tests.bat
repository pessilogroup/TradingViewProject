@echo off
echo ========================================
echo Running Unit, Integration, and Security Tests
echo ========================================

pytest tests/unit tests/integration tests/security -v

if %errorlevel% neq 0 (
    echo [!] Tests FAILED.
    exit /b %errorlevel%
) else (
    echo [OK] Tests PASSED.
)
