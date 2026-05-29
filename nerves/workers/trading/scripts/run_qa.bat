@echo off
echo ========================================
echo Running QA Checks (Linter & Type Checker)
echo ========================================

echo.
echo [1/2] Running Ruff (Linter & Formatter)
ruff check .

echo.
echo [2/2] Running Mypy (Type Checker)
mypy . --ignore-missing-imports

echo.
if %errorlevel% neq 0 (
    echo [!] QA Checks FAILED. Please fix the issues above.
    exit /b %errorlevel%
) else (
    echo [OK] QA Checks PASSED.
)
