@echo off
setlocal enabledelayedexpansion
title AutoDeck Lite Build


cd /d "%~dp0"

if defined ADBCONTROL_PIP_INDEX_URL (
  set "PIP_MIRROR_URL=%ADBCONTROL_PIP_INDEX_URL%"
) else (
  set "PIP_MIRROR_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
)

if defined ADBCONTROL_PIP_TRUSTED_HOST (
  set "PIP_TRUSTED_HOST=%ADBCONTROL_PIP_TRUSTED_HOST%"
) else (
  set "PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn"
)

if defined ADBCONTROL_NPM_REGISTRY (
  set "NPM_REGISTRY_URL=%ADBCONTROL_NPM_REGISTRY%"
) else (
  set "NPM_REGISTRY_URL=https://registry.npmmirror.com"
)

set "PYTHON_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
)

echo ============================================================
echo           AutoDeck Lite Build (精简版)
echo ============================================================
echo.
echo [INFO] 此版本不包含以下大型依赖：
echo   - PyTorch (~500 MB)
echo   - Transformers (~100 MB)
echo   - SciPy (~110 MB)
echo   - LLVM/numba (~130 MB)
echo   - nagisa/gradio (~85 MB)
echo.
echo [INFO] 预估打包大小：~150 MB (原版 ~405 MB)
echo.
echo [WARNING] 精简版不支持以下功能：
echo   - DINOv2 图像比对（仅支持 OpenCV）
echo   - ASR 语音识别
echo.
echo ============================================================
echo.

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
      echo - Installing dependencies with npm ci via %NPM_REGISTRY_URL% ...
      call npm ci --registry=%NPM_REGISTRY_URL%
      if errorlevel 1 (
        echo - npm ci failed, falling back to npm install via %NPM_REGISTRY_URL% ...
        call npm install --registry=%NPM_REGISTRY_URL%
      )
    ) else (
      echo - Installing dependencies with npm install via %NPM_REGISTRY_URL% ...
      call npm install --registry=%NPM_REGISTRY_URL%
    )
  )
  if errorlevel 1 goto :npm_fail
  if not exist "node_modules\.bin\vite.cmd" (
    echo Frontend dependencies are incomplete.
    echo If esbuild.exe is in use, close the frontend dev server or the esbuild terminal and run build_exe_lite.bat again.
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
echo - Using pip mirror: %PIP_MIRROR_URL%
"%PYTHON_CMD%" -m pip install --upgrade pip -i "%PIP_MIRROR_URL%" --trusted-host "%PIP_TRUSTED_HOST%"
if errorlevel 1 (
  echo pip upgrade failed
  pause
  exit /b 1
)
"%PYTHON_CMD%" -m pip install pyinstaller -i "%PIP_MIRROR_URL%" --trusted-host "%PIP_TRUSTED_HOST%"
if errorlevel 1 (
  echo PyInstaller installation failed
  pause
  exit /b 1
)

if exist "backend\requirements.txt" (
  echo - Installing dependencies from requirements.txt
  "%PYTHON_CMD%" -m pip install -r backend\requirements.txt -i "%PIP_MIRROR_URL%" --trusted-host "%PIP_TRUSTED_HOST%"
  if errorlevel 1 (
    echo Dependencies installation failed
    pause
    exit /b 1
  )
)

echo [4/4] Building EXE (Lite)
if exist "dist\AutoDeck_lite.exe" (
  echo - Stopping running AutoDeck_lite.exe processes that would lock dist\AutoDeck_lite.exe
  taskkill /f /im AutoDeck_lite.exe >nul 2>nul
)
if exist "dist" (
  echo - Cleaning old dist directory
  call :remove_dir_with_retry dist
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
if exist "build" (
  echo - Cleaning old build directory
  call :remove_dir_with_retry build
  if errorlevel 1 (
    pause
    exit /b 1
  )
)

if not exist "frontend\dist\index.html" (
  echo Frontend build output not found: frontend\dist\index.html
  pause
  exit /b 1
)

if not exist "AutoDeck_lite.spec" (
  echo AutoDeck_lite.spec not found
  pause
  exit /b 1
)

"%PYTHON_CMD%" -m PyInstaller --clean --noconfirm AutoDeck_lite.spec
if errorlevel 1 (
  echo Build failed
  pause
  exit /b 1
)

echo.
echo ============================================================
echo           Build completed (精简版)
echo ============================================================
echo - Executable: "%~dp0dist\AutoDeck_lite.exe"
echo - Visit after start: http://localhost:8000/
echo.
echo [INFO] 精简版功能：
echo   ✓ 采集卡录屏
echo   ✓ OpenCV 图像比对
echo   ✓ Excel 执行
echo   ✓ ADB 控制
echo   ✓ 报告生成
echo.
echo [INFO] 不支持的功能：
echo   ✗ DINOv2 图像比对
echo   ✗ ASR 语音识别
echo ============================================================
echo.
pause
exit /b 0

:npm_fail
popd
echo Frontend build failed
pause
exit /b 1

:remove_dir_with_retry
set "TARGET_DIR=%~1"
for /l %%I in (1,1,5) do (
  if not exist "%TARGET_DIR%" exit /b 0
  rmdir /s /q "%TARGET_DIR%" >nul 2>nul
  if not exist "%TARGET_DIR%" exit /b 0
  if %%I lss 5 (
    echo   - Retry %%I/5: waiting for "%TARGET_DIR%" to be released...
    timeout /t 1 /nobreak >nul
  )
)
echo Failed to clean "%TARGET_DIR%". Files in this directory are still in use.
if /i "%TARGET_DIR%"=="dist" (
  echo Please close any running AutoDeck_lite.exe window and try again.
)
exit /b 1
