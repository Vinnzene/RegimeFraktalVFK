# scripts/launch_demo.ps1
# Peluncur Satu Perintah untuk Sidang Skripsi (UBM 2026)
# Menjalankan Backend FastAPI dan Frontend Next.js 100% Offline

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BTC/USDT Regime Dashboard - Peluncur Mode Demo Offline    " -ForegroundColor Cyan
Write-Host "  Topik Skripsi: Identifikasi Regime Fraktal Dinamis       " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Verifikasi Kesiapan Offline
Write-Host "`n[1/4] Memeriksa kelengkapan file data dan model..." -ForegroundColor Yellow
python "$Root\scripts\check_offline_ready.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Ada file data/artefak yang hilang. Jalankan pipeline terlebih dahulu." -ForegroundColor Red
    exit 1
}

# 2. Menjalankan Backend FastAPI
Write-Host "`n[2/4] Menjalankan Backend FastAPI (port 8000)..." -ForegroundColor Yellow
$BackendDir = Join-Path $Root "backend"
$BackendProcess = Start-Process python -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $BackendDir -PassThru

# Menunggu Backend Siap
$BackendReady = $false
$Retries = 30
while (-not $BackendReady -and $Retries -gt 0) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/meta/config" -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -eq 200) {
            $BackendReady = $true
        }
    } catch {
        $Retries--
    }
}

if (-not $BackendReady) {
    Write-Host "[ERROR] Backend gagal merespons setelah 30 detik." -ForegroundColor Red
    Stop-Process -Id $BackendProcess.Id -Force
    exit 1
}
Write-Host "[OK] Backend aktif di http://127.0.0.1:8000" -ForegroundColor Green

# 3. Menjalankan Frontend Next.js
Write-Host "`n[3/4] Menjalankan Frontend Next.js (port 3000)..." -ForegroundColor Yellow
$FrontendDir = Join-Path $Root "frontend"
$FrontendProcess = Start-Process npm.cmd -ArgumentList "run dev" -WorkingDirectory $FrontendDir -PassThru

# Menunggu Frontend Siap
$FrontendReady = $false
$Retries = 40
while (-not $FrontendReady -and $Retries -gt 0) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -eq 200) {
            $FrontendReady = $true
        }
    } catch {
        $Retries--
    }
}

if (-not $FrontendReady) {
    Write-Host "[PERINGATAN] Frontend masih melakukan kompilasi; membuka browser..." -ForegroundColor Yellow
} else {
    Write-Host "[OK] Frontend aktif di http://localhost:3000" -ForegroundColor Green
}

# 4. Membuka Browser
Write-Host "`n[4/4] Membuka Dashboard di Browser..." -ForegroundColor Yellow
Start-Process "http://localhost:3000"

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  DASHBOARD BERHASIL DILUNCURKAN DALAM MODE OFFLINE!        " -ForegroundColor Green
Write-Host "  Backend PID: $($BackendProcess.Id) | Frontend PID: $($FrontendProcess.Id)" -ForegroundColor Gray
Write-Host "  Tekan sembarang tombol untuk menghentikan server demo...  " -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Write-Host "`nMematikan server..." -ForegroundColor Yellow
Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue
Write-Host "Selesai. Server demo telah ditutup." -ForegroundColor Green
