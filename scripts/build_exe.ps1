# Build portable TCC-App folder (PyInstaller onedir).
# Usage (from repo root, with Python 3.10-3.12):
#   .\scripts\build_exe.ps1
#
# Output: dist\TCC-App\  -> zip that folder and ship it.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Find-Python312 {
    foreach ($ver in @("3.12", "3.11", "3.10")) {
        try {
            $exe = & py "-$ver" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) {
                return ($exe | Out-String).Trim()
            }
        } catch { }
    }
    throw "Python 3.10-3.12 required (3.14 breaks PyAudio). Install from python.org and retry."
}

Write-Host "==> Python..." -ForegroundColor Cyan
$Py = Find-Python312
Write-Host "    $Py"

$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "==> Creating .venv..." -ForegroundColor Cyan
    & $Py -m venv .venv
}
$VenvPy = (Resolve-Path $VenvPy).Path
Write-Host "    venv: $VenvPy"

Write-Host "==> Installing dependencies + PyInstaller..." -ForegroundColor Cyan
& $VenvPy -m pip install --upgrade pip
& $VenvPy -m pip install -r requirements.txt
& $VenvPy -m pip install "pyinstaller>=6.0"

Write-Host "==> Downloading MediaPipe models..." -ForegroundColor Cyan
& $VenvPy scripts\download_models.py
if ($LASTEXITCODE -ne 0) { throw "download_models.py failed" }

$VoskDir = Join-Path $Root "models\vosk-model-pt-fb-v0.1.1-pruned"
if (-not (Test-Path $VoskDir)) {
    Write-Host "==> Downloading Vosk PT-BR model (large, one-time)..." -ForegroundColor Cyan
    & $VenvPy scripts\download_vosk_model.py
    if ($LASTEXITCODE -ne 0) { throw "download_vosk_model.py failed" }
} else {
    Write-Host "==> Vosk model already present - skip." -ForegroundColor DarkGray
}

$PwCache = Join-Path $Root "build_assets\ms-playwright"
$chromiumOk = Get-ChildItem -Path $PwCache -Directory -Filter "chromium-*" -ErrorAction SilentlyContinue
if (-not $chromiumOk) {
    Write-Host "==> Installing Playwright Chromium into build_assets..." -ForegroundColor Cyan
    if (Test-Path $PwCache) { Remove-Item $PwCache -Recurse -Force }
    New-Item -ItemType Directory -Path $PwCache -Force | Out-Null
    $env:PLAYWRIGHT_BROWSERS_PATH = $PwCache
    & $VenvPy -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "playwright install chromium failed" }
} else {
    Write-Host "==> Playwright Chromium already in build_assets - skip." -ForegroundColor DarkGray
}

Write-Host "==> PyInstaller build..." -ForegroundColor Cyan
# OneDrive/AV often locks dist\; rename aside so COLLECT can recreate it.
if (Test-Path (Join-Path $Root "dist\TCC-App")) {
    $bak = Join-Path $Root ("dist\TCC-App.bak-" + (Get-Date -Format "HHmmss"))
    try {
        Rename-Item (Join-Path $Root "dist\TCC-App") $bak
        Write-Host "    moved old dist -> $bak"
    } catch {
        Write-Warning "Could not rename dist\TCC-App (close TCC-App.exe / pause OneDrive sync). Retrying in place."
    }
}
& $VenvPy -m PyInstaller --noconfirm tcc_app.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$Dist = Join-Path $Root "dist\TCC-App"
if (-not (Test-Path (Join-Path $Dist "TCC-App.exe"))) {
    throw "Expected dist\TCC-App\TCC-App.exe missing"
}

Write-Host "==> Copying portable assets next to the exe..." -ForegroundColor Cyan
# Full Playwright browser tree (headed + headless shell).
$PwDst = Join-Path $Dist "ms-playwright"
if (Test-Path $PwDst) { Remove-Item $PwDst -Recurse -Force }
Copy-Item $PwCache $PwDst -Recurse -Force
Write-Host "    build_assets\ms-playwright -> ms-playwright"

$assets = @(
    @{ Src = "models"; Dst = "models" },
    @{ Src = "config\commands.yaml"; Dst = "config\commands.yaml" },
    @{ Src = "mapeamento.json"; Dst = "mapeamento.json" }
)
foreach ($a in $assets) {
    $src = Join-Path $Root $a.Src
    $dst = Join-Path $Dist $a.Dst
    if (-not (Test-Path $src)) {
        Write-Warning "Missing asset: $($a.Src) - skipped"
        continue
    }
    $dstParent = Split-Path $dst -Parent
    if (-not (Test-Path $dstParent)) {
        New-Item -ItemType Directory -Path $dstParent | Out-Null
    }
    if (Test-Path $src -PathType Container) {
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        Copy-Item $src $dst -Recurse -Force
    } else {
        Copy-Item $src $dst -Force
    }
    Write-Host "    $($a.Src) -> $($a.Dst)"
}

$state = Join-Path $Dist "config\app_state.json"
if (Test-Path $state) { Remove-Item $state -Force }

Write-Host ""
Write-Host "OK - pasta pronta:" -ForegroundColor Green
Write-Host "  $Dist"
Write-Host "Zippe dist\TCC-App e envie. O usuario so precisa extrair e abrir TCC-App.exe"
Write-Host ""
Write-Host "Incluido: MediaPipe, Vosk, Playwright Chromium (comandos de voz no navegador)."
Write-Host "Nota: Whisper ainda baixa na 1a uso (internet)."
