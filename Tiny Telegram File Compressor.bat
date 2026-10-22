@echo off
setlocal
title Tiny Telegram File Compressor
cd /d "%~dp0"
echo Tiny Telegram File Compressor
echo 7z - 2000 MB maximum per part - Normal compression.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -u compresser_dossiers.py
) else (
    python -u compresser_dossiers.py
)
echo.
pause
