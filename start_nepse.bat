@echo off
setlocal
title Nepse CLI Launcher

echo [INFO] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.7+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [INFO] Ensuring Nepse CLI is installed...
pip install -e . >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [INFO] Launching...
cls
nepse
