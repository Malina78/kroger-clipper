@echo off
title Kroger Coupon Clipper 🛒
echo ============================================
echo  Kroger Coupon Clipper v1.0
echo ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

python -c "import playwright" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Playwright not installed!
    echo Run: pip install playwright
    pause
    exit /b 1
)

echo [INFO] Starting Kroger coupon clipper...
echo [INFO] Do NOT close this window while running.
echo.

python "%~dp0kroger_clip.py"

echo.
echo ============================================
echo  Done! Press any key to close.
echo ============================================
pause
