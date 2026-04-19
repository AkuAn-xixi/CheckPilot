@echo off
setlocal enabledelayedexpansion
title ADBControl Build


cd /d "%~dp0"

echo [1/4] Checking environment: Node.js / Python / pip
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js not found. Please install https://nodejs.org/ and add it to PATH.
  pause
  exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Please install https://www.python.org/ and add it to PATH.
  pause
  exit /b 1
)

echo [2/4] Frontend build (frontend)
if exist "frontend\package.json" (
  pushd frontend
  echo - Installing dependencies...
  call npm install
  if errorlevel 1 goto :npm_fail
  echo - Building production bundle...
  call npm run build
  if errorlevel 1 goto :npm_fail
  popd
) else (
  echo - frontend\package.json not found, skipping frontend build
)

echo [3/4] Installing dependencies
python -m pip install --upgrade pip
python -m pip install pyinstaller
if errorlevel 1 (
  echo PyInstaller installation failed
  pause
  exit /b 1
)

if exist "backend\requirements.txt" (
  echo - Installing dependencies from requirements.txt
  python -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo Dependencies installation failed
    pause
    exit /b 1
  )
)

echo [4/4] Building EXE
if exist "dist" (
  echo - Cleaning old dist directory
  rmdir /s /q dist
)
if exist "build" (
  echo - Cleaning old build directory
  rmdir /s /q build
)

REM Add common hidden imports to avoid missing modules at runtime
pyinstaller --onefile --name ADBControl ^
  --hidden-import anyio ^
  --hidden-import uvicorn ^
  --hidden-import fastapi ^
  --hidden-import starlette ^
  --hidden-import pydantic ^
  --hidden-import pandas ^
  --hidden-import numpy ^
  --collect-all pydantic ^
  --collect-all starlette ^
  --collect-all pandas ^
  --collect-all numpy ^
  --add-data "frontend\dist;frontend\dist" ^
  run_app.py
if errorlevel 1 (
  echo Build failed
  pause
  exit /b 1
)

echo.
echo Build completed:
echo - Executable: "%~dp0dist\ADBControl.exe"
echo - Visit after start: http://localhost:8000/
echo.
pause
exit /b 0

:npm_fail
echo Frontend build failed
pause
exit /b 1
