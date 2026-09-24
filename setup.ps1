# Setup otomatis toolkit riset meme di Windows (PowerShell).
#
#   .\setup.ps1                       # setup penuh, lalu wizard login
#   .\setup.ps1 -SkipLogin            # setup saja
#   .\setup.ps1 -Python "C:\path\python.exe"
#
# Kalau muncul error "running scripts is disabled", jalankan sekali:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

param(
    [string]$Python = "",
    [switch]$SkipLogin,
    [switch]$SkipNode
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    OK  $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    !!  $msg" -ForegroundColor Yellow }

function Ask-Install($name, $wingetId) {
    $ans = Read-Host "    $name belum ada. Pasang lewat winget ($wingetId)? [y/N]"
    if ($ans -match '^[yY]') {
        winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
        Warn "Tutup dan buka lagi PowerShell supaya PATH terbaru terbaca, lalu jalankan .\setup.ps1 lagi."
        exit 0
    }
    return $false
}

# ---------- Python ----------
Step "Mencari Python 3.10+"
if (-not $Python) {
    foreach ($cand in @("py -3.12", "py -3", "python")) {
        try {
            $v = & cmd /c "$cand -c `"import sys;print(sys.version_info[:2]>=(3,10))`" 2>nul"
            if ($v -eq "True") { $Python = $cand; break }
        } catch {}
    }
}
if (-not $Python) {
    Warn "Python 3.10+ tidak ditemukan. Pasang dari https://www.python.org/downloads/ (centang 'Add to PATH')"
    Warn "atau jalankan: .\setup.ps1 -Python `"C:\Users\<nama>\AppData\Local\Programs\Python\Python312\python.exe`""
    exit 1
}
Ok "pakai: $Python"

# ---------- venv ----------
Step "Virtual environment .venv"
if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    & cmd /c "$Python -m venv `"$Root\.venv`""
    Ok "dibuat"
} else { Ok "sudah ada" }
$VPy = "$Root\.venv\Scripts\python.exe"

Step "Memasang paket Python (requirements.txt)"
& $VPy -m pip install --upgrade pip --quiet
& $VPy -m pip install -r "$Root\requirements.txt" --quiet
Ok "selesai"

# ---------- ffmpeg ----------
Step "ffmpeg"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Ok ((ffmpeg -version | Select-Object -First 1) -replace ' Copyright.*','')
} else {
    Ask-Install "ffmpeg" "Gyan.FFmpeg" | Out-Null
    Warn "ffmpeg tidak ada: yt-dlp tetap jalan tapi tidak bisa menggabung audio+video kualitas tinggi."
}

# ---------- Node.js ----------
if (-not $SkipNode) {
    Step "Node.js + crawlee/playwright"
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Ask-Install "Node.js" "OpenJS.NodeJS.LTS" | Out-Null
        Warn "Node.js dilewati (crawlee/playwright tidak dipasang). Ulangi dengan -SkipNode untuk menyembunyikan pesan ini."
    } else {
        Push-Location "$Root\node"
        npm install --no-audit --no-fund --loglevel=error
        npx playwright install chromium
        Pop-Location
        Ok "node $(node --version), crawlee + playwright + chromium"
    }
}

# ---------- folder & .env ----------
Step "Folder dan .env"
foreach ($d in @("data", "downloads")) { New-Item -ItemType Directory -Force -Path "$Root\$d" | Out-Null }
if (-not (Test-Path "$Root\.env")) {
    Copy-Item "$Root\.env.example" "$Root\.env"
    Ok ".env dibuat dari .env.example (kosong, diisi lewat wizard login)"
} else { Ok ".env sudah ada, tidak diubah" }

# ---------- verifikasi ----------
Step "Verifikasi tool"
& $VPy -m yt_dlp --version     | ForEach-Object { Ok "yt-dlp $_" }
& $VPy -m gallery_dl --version | ForEach-Object { Ok "gallery-dl $_" }
& $VPy -m instaloader --version | ForEach-Object { Ok "instaloader $_" }
& $VPy -c "import praw, scrapy; print('praw', praw.__version__, '| scrapy', scrapy.__version__)" | ForEach-Object { Ok $_ }

Write-Host "`nSetup selesai." -ForegroundColor Green
Write-Host "Aktifkan venv di terminal baru dengan:  .\.venv\Scripts\Activate.ps1`n"

if (-not $SkipLogin) {
    Step "Wizard login sosial media"
    & $VPy "$Root\scripts\login.py"
} else {
    Write-Host "Untuk login sosmed nanti:  .\.venv\Scripts\python.exe scripts\login.py"
}
