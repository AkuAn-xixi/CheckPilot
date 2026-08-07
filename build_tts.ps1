# AutoDeck TTS Build Script
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "       AutoDeck TTS Build" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "TTS/ASR Version with PyTorch + Transformers" -ForegroundColor Yellow
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

# Check TTS dependencies
Write-Host ""
Write-Host "[2/3] Checking TTS dependencies..." -ForegroundColor Yellow
$ttsPackages = @("torch", "transformers", "qwen_asr", "scipy", "librosa")
$missingPackages = @()

foreach ($pkg in $ttsPackages) {
    try {
        & $pythonCmd -c "import $pkg" 2>$null
        Write-Host "  $pkg - OK" -ForegroundColor Green
    } catch {
        Write-Host "  $pkg - MISSING" -ForegroundColor Red
        $missingPackages += $pkg
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing packages: $($missingPackages -join ', ')" -ForegroundColor Red
    Write-Host "Install with: pip install $($missingPackages -join ' ')" -ForegroundColor Yellow
    $install = Read-Host "Install now? (y/n)"
    if ($install -eq "y") {
        & $pythonCmd -m pip install $missingPackages
    }
}

# Build Frontend
Write-Host ""
Write-Host "[3/4] Building Frontend..." -ForegroundColor Yellow
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
Write-Host "[4/4] Building EXE..." -ForegroundColor Yellow

if (Test-Path ".\dist\AutoDeck_tts.exe") {
    Stop-Process -Name "AutoDeck_tts" -Force -ErrorAction SilentlyContinue
}

if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" }
if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" }

& $pythonCmd -m PyInstaller --clean --noconfirm AutoDeck_tts.spec

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
Write-Host "EXE: $PSScriptRoot\dist\AutoDeck_tts.exe" -ForegroundColor Cyan
Write-Host ""

# Show file size
$exePath = ".\dist\AutoDeck_tts.exe"
if (Test-Path $exePath) {
    $size = (Get-Item $exePath).Length / 1MB
    Write-Host "File size: $([math]::Round($size, 2)) MB" -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Press Enter to exit"
