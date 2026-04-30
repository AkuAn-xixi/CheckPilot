@echo off
setlocal enabledelayedexpansion
title ADBControl Build


cd /d "%~dp0"

set "PYTHON_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
)

echo [1/4] Checking environment: Node.js / Python / pip
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js not found. Please install https://nodejs.org/ and add it to PATH.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo npm not found. Please ensure Node.js is installed correctly.
  pause
  exit /b 1
)
"%PYTHON_CMD%" --version >nul 2>nul
if errorlevel 1 (
  echo Python runtime not found. Please install Python or create .venv first.
  pause
  exit /b 1
)

echo [2/4] Frontend build (frontend)
if exist "frontend\package.json" (
  pushd frontend
  if exist "node_modules\.bin\vite.cmd" (
    echo - Reusing existing frontend dependencies
  ) else (
    if exist "package-lock.json" (
      echo - Installing dependencies with npm ci...
      call npm ci
      if errorlevel 1 (
        echo - npm ci failed, falling back to npm install...
        call npm install
      )
    ) else (
      echo - Installing dependencies with npm install...
      call npm install
    )
  )
  if errorlevel 1 goto :npm_fail
  if not exist "node_modules\.bin\vite.cmd" (
    echo Frontend dependencies are incomplete.
    echo If esbuild.exe is in use, close the frontend dev server or the esbuild terminal and run build_exe.bat again.
    goto :npm_fail
  )
  echo - Building production bundle...
  call npm run build
  if errorlevel 1 goto :npm_fail
  popd
) else (
  echo - frontend\package.json not found, skipping frontend build
)

echo [3/4] Installing dependencies
"%PYTHON_CMD%" -m pip install --upgrade pip
"%PYTHON_CMD%" -m pip install pyinstaller
if errorlevel 1 (
  echo PyInstaller installation failed
  pause
  exit /b 1
)

if exist "backend\requirements.txt" (
  echo - Installing dependencies from requirements.txt
  "%PYTHON_CMD%" -m pip install -r backend\requirements.txt
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

if not exist "frontend\dist\index.html" (
  echo Frontend build output not found: frontend\dist\index.html
  pause
  exit /b 1
)

if not exist "ADBControl.spec" (
  echo ADBControl.spec not found
  pause
  exit /b 1
)

"%PYTHON_CMD%" -m PyInstaller --clean --noconfirm ADBControl.spec
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
popd
echo Frontend build failed
pause
exit /b 1
