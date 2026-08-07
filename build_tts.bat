@echo off
setlocal enabledelayedexpansion
title AutoDeck TTS Build

cd /d "%~dp0"

set "PYTHON_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
)

echo ============================================
echo        AutoDeck TTS Build
echo ============================================
echo.
echo TTS/ASR Version with PyTorch + Transformers
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
echo [2/3] Checking TTS dependencies...
"%PYTHON_CMD%" -c "import torch; print('torch OK')" 2>nul || echo torch MISSING
"%PYTHON_CMD%" -c "import transformers; print('transformers OK')" 2>nul || echo transformers MISSING
"%PYTHON_CMD%" -c "import qwen_asr; print('qwen_asr OK')" 2>nul || echo qwen_asr MISSING
"%PYTHON_CMD%" -c "import scipy; print('scipy OK')" 2>nul || echo scipy MISSING
"%PYTHON_CMD%" -c "import librosa; print('librosa OK')" 2>nul || echo librosa MISSING

echo.
echo [3/4] Building Frontend...
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
echo [4/4] Building EXE...
if exist "dist\AutoDeck_tts.exe" (
  taskkill /f /im AutoDeck_tts.exe >nul 2>nul
)

if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

"%PYTHON_CMD%" -m PyInstaller --clean --noconfirm AutoDeck_tts.spec
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
echo EXE: %~dp0dist\AutoDeck_tts.exe
echo.
pause
