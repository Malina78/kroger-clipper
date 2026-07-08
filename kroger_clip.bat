@echo off
title Kroger Coupon Clipper
cd /d "%~dp0"
echo Starting Kroger Coupon Clipper...
python kroger_clip.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error! Press any key to exit.
    pause >nul
)
