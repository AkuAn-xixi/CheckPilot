@echo off
setlocal enabledelayedexpansion
title AutoDeck Lite Build

cd /d "%~dp0"

set "PYTHON_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
)

echo ============================================
echo        AutoDeck Lite Build
echo ============================================
echo.

echo [1/3] Checking Python...
"%PYTHON_CMD%" --version >nul 2>nul
if errorlevel 1 (
  echo Python not found!
  pause
  exit /b 1
)
echo Python OK

echo.
echo [2/3] Building Frontend...
if exist "frontend\package.json" (
  cd frontend
  if not exist "node_modules\.bin\vite.cmd" (
    call npm install
  )
  call npm run build
  cd ..
)
echo Frontend OK

echo.
echo [3/3] Building EXE...
if exist "dist\AutoDeck_lite.exe" (
  taskkill /f /im AutoDeck_lite.exe >nul 2>nul
)

if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

"%PYTHON_CMD%" -m PyInstaller --clean --noconfirm AutoDeck_lite.spec
if errorlevel 1 (
  echo Build failed!
  pause
  exit /b 1
)

echo.
echo ============================================
echo        Build completed!
echo ============================================
echo.
echo EXE: %~dp0dist\AutoDeck_lite.exe
echo.
pause
