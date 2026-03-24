$ErrorActionPreference = "Stop"

function Die($m) {
    Write-Host ""
    Write-Host "FAILED: $m" -ForegroundColor Red
    throw $m
}

function Get-FreePort {
    $ports = 8011..8025
    foreach ($p in $ports) {
        try {
            $used = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
            if (-not $used) { return $p }
        } catch {
            return $p
        }
    }
    return 8011
}

Write-Host ""
Write-Host ("=" * 72) -ForegroundColor Cyan
Write-Host "Portable Memory MVP - Startup" -ForegroundColor Green
Write-Host ("=" * 72) -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Die "python not found in PATH"
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

$Py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Die "venv python missing at $Py"
}

Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $Py -m pip install --upgrade pip | Out-Null
& $Py -m pip install -r .\requirements.txt

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "sqlite:///./portable_memory.db"
}

$Port = Get-FreePort
Write-Host "Using port $Port" -ForegroundColor Yellow

$Server = Start-Process `
  -FilePath $Py `
  -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port","$Port" `
  -WorkingDirectory (Get-Location).Path `
  -PassThru

Start-Sleep -Seconds 5

try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/docs"
    if ($resp.StatusCode -ne 200) {
        Die "Server started but docs endpoint did not return 200"
    }
} catch {
    Die "Could not reach docs endpoint on port $Port"
}

$result = @{
    ok = $true
    port = $Port
    docs_url = "http://127.0.0.1:$Port/docs"
    server_pid = $Server.Id
} | ConvertTo-Json -Depth 5

Set-Content -LiteralPath ".\startup-results.json" -Value $result -Encoding UTF8

Write-Host ""
Write-Host "SUCCESS" -ForegroundColor Green
Write-Host "Docs: http://127.0.0.1:$Port/docs" -ForegroundColor Yellow
Write-Host "Startup results: .\startup-results.json" -ForegroundColor Yellow
Write-Host "Stop later with: Stop-Process -Id $($Server.Id)" -ForegroundColor Yellow
