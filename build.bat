@echo off
title Build YTDownloader
cd /d "%~dp0"

echo.
echo  [1/3] Installing build tools...
py -m pip install pyinstaller flask -q --upgrade
if errorlevel 1 (
    echo ERROR: pip install failed. Make sure Python is installed.
    pause & exit /b 1
)

echo.
echo  [2/3] Building with PyInstaller...
py -m PyInstaller YTDownloader.spec --noconfirm --clean
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause & exit /b 1
)

echo.
echo  [3/3] Done!
echo.
echo  Output folder: dist\YTDownloader\
echo  Share that entire folder — users double-click YTDownloader.exe
echo.
pause
