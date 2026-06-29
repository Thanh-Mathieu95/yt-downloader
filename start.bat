@echo off
title YouTube Downloader
cd /d "%~dp0"

echo.
echo  Checking dependencies...
py -m pip install "flask>=3.0" "yt-dlp>=2026.3.17" -q --upgrade

echo.
echo  Starting YouTube Downloader...
echo  Open your browser at: http://localhost:5000
echo.
start "" "http://localhost:5000"
py app.py
pause
