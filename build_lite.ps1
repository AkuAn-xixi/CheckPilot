# AutoDeck Lite Build Script
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "       AutoDeck Lite Build" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

# Check Python
Write-Host "[1/3] Checking Python..." -ForegroundColor Yellow
$pythonCmd = "python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $pythonCmd = ".\.venv\Scripts\python.exe"
}

try {
    & $pythonCmd --version
    Write-Host "Python OK" -ForegroundColor Green
} catch {
    Write-Host "Python not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Build Frontend
Write-Host ""
Write-Host "[2/3] Building Frontend..." -ForegroundColor Yellow
if (Test-Path ".\frontend\package.json") {
    Push-Location frontend
    if (-not (Test-Path ".\node_modules\.bin\vite.cmd")) {
        npm install
    }
    npm run build
    Pop-Location
}
Write-Host "Frontend OK" -ForegroundColor Green

# Build EXE
Write-Host ""
Write-Host "[3/3] Building EXE..." -ForegroundColor Yellow

if (Test-Path ".\dist\AutoDeck_lite.exe") {
    Stop-Process -Name "AutoDeck_lite" -Force -ErrorAction SilentlyContinue
}

if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" }
if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" }

& $pythonCmd -m PyInstaller --clean --noconfirm AutoDeck_lite.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "       Build completed!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "EXE: $PSScriptRoot\dist\AutoDeck_lite.exe" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
