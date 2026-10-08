# AccessAI Demo Launcher (Windows PowerShell)
# Usage: .\run_demo.ps1  OR  make demo

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host '==========================================================' -ForegroundColor Cyan
Write-Host '  AccessAI - AVINYA 2K26 (IIT Kanpur) Demo Launcher' -ForegroundColor Cyan
Write-Host '  Offline-First AI for Rural Welfare and Opportunities' -ForegroundColor Cyan
Write-Host '==========================================================' -ForegroundColor Cyan

# 1. Ensure .env exists
if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host '[setup] .env created from .env.example' -ForegroundColor Yellow
}

# 2. Ensure Ed25519 Keys exist
if (-not (Test-Path 'keys\private.key')) {
    Write-Host '[setup] Generating Ed25519 keypair...' -ForegroundColor Yellow
    python -c "from shared.packet import ensure_keys; ensure_keys(); print('[setup] Ed25519 Keypair ready.')"
}

# 3. Clean packets folder and seed databases
Write-Host '[setup] Seeding databases from real notices and personas...' -ForegroundColor Yellow
if (-not (Test-Path 'packets')) {
    New-Item -ItemType Directory -Force -Path 'packets' | Out-Null
}
python cloud/seed.py
python hub/seed.py

# 4. Sign and broadcast official notice packets
Write-Host '[setup] Signing and broadcasting official notice packets...' -ForegroundColor Yellow
python cloud/publish_sample.py --approve-all

Write-Host ''
Write-Host '==========================================================' -ForegroundColor Green
Write-Host '  Services Ready:' -ForegroundColor Green
Write-Host '  [Cloud Control Center] -> http://localhost:8000' -ForegroundColor Green
Write-Host '  [Village Hub PWA]      -> http://localhost:8001' -ForegroundColor Green
Write-Host '==========================================================' -ForegroundColor Green
Write-Host ''

# 5. Launch both servers in separate windows
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ScriptDir'; python -m uvicorn cloud.main:app --port 8000" -WindowStyle Normal
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ScriptDir'; python -m uvicorn hub.main:app --port 8001" -WindowStyle Normal

Start-Sleep -Seconds 2
Start-Process 'http://localhost:8000'
Start-Process 'http://localhost:8001'

Write-Host '[demo] Both services launched and browser tabs opened.' -ForegroundColor Cyan
