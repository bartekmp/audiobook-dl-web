# Windows startup script for audiobook-dl-web
# PowerShell version

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "audiobook-dl-web - Windows Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.14 or higher from https://www.python.org/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create virtual environment
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "  Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "  Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "[3/5] Activating virtual environment..." -ForegroundColor Yellow
$activateScript = ".\venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
    Write-Host "  Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "ERROR: Failed to find activation script" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Install dependencies
Write-Host "[4/5] Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
pip install -e .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "  Dependencies installed" -ForegroundColor Green

# Create directories
Write-Host "[5/5] Creating directories..." -ForegroundColor Yellow
if (-not (Test-Path "config")) {
    New-Item -ItemType Directory -Path "config" | Out-Null
}
if (-not (Test-Path "downloads")) {
    New-Item -ItemType Directory -Path "downloads" | Out-Null
}
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}
Write-Host "  Directories ready" -ForegroundColor Green

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Application will start at http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Start application
python -m app.main
