$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "webapp\backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   EDAFIX - INICIO DE SERVIDORES (WINDOWS)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/3] Creando entorno virtual de Python en Windows..." -ForegroundColor Yellow
    py -m venv (Join-Path $BackendDir ".venv")
}

Write-Host "[2/3] Verificando dependencias de Python..." -ForegroundColor Yellow
& $VenvPython -c "import fastapi, uvicorn, PIL, multipart" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
}

Write-Host "[3/3] Levantando servidor FastAPI + Frontend en http://localhost:8000 ..." -ForegroundColor Green
Write-Host "🌐 Abre en tu navegador: http://localhost:8000" -ForegroundColor Green
Write-Host "⚙️  Documentacion API:   http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""

Set-Location $BackendDir
& $VenvPython -m uvicorn main:app --host 0.0.0.0 --port 8000

