@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo 3D Print App Launcher
echo ========================================
echo.

where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo uv was not found. Installing uv...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if %errorlevel% neq 0 (
        echo.
        echo Failed to install uv automatically.
        echo Install uv manually and run this file again.
        pause
        exit /b 1
    )

    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

echo Syncing project dependencies...
call uv sync
if %errorlevel% neq 0 (
    echo.
    echo Failed to sync dependencies.
    pause
    exit /b 1
)

echo.
echo Launching app...
call uv run -m src.app

echo.
echo App process ended.
pause
