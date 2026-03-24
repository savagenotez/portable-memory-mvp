$ErrorActionPreference = 'Stop'

function Write-Banner($text) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor Cyan
    Write-Host $text -ForegroundColor Green
    Write-Host ('=' * 72) -ForegroundColor Cyan
}

function Assert-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $name"
    }
}

function Invoke-JsonPost($url, $filePath) {
    $json = Get-Content -LiteralPath $filePath -Raw
    Invoke-RestMethod -Method Post -Uri $url -ContentType 'application/json' -Body $json
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Banner 'Portable Memory MVP bootstrap starting'

Assert-Command python

if (-not (Test-Path '.venv')) {
    Write-Host '[1/8] Creating virtual environment...'
    python -m venv .venv
} else {
    Write-Host '[1/8] Virtual environment already exists.'
}

$Py = Join-Path $Root '.venv\Scripts\python.exe'
$Pip = Join-Path $Root '.venv\Scripts\pip.exe'

Write-Host '[2/8] Installing dependencies...'
& $Py -m pip install --upgrade pip | Out-Null
& $Pip install -r requirements.txt

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = 'sqlite:///./portable_memory.db'
    Write-Host '[3/8] DATABASE_URL not set. Using SQLite default.' -ForegroundColor Yellow
} else {
    Write-Host "[3/8] Using DATABASE_URL=$($env:DATABASE_URL)"
}

Write-Host '[4/8] Starting FastAPI server...'
$Server = Start-Process -FilePath $Py -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $Root -PassThru

try {
    Write-Host '[5/8] Waiting for server health check...'
    $Healthy = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $Health = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/v1/health'
            if ($Health.status -eq 'ok') {
                $Healthy = $true
                break
            }
        } catch {
        }
    }
    if (-not $Healthy) {
        throw 'Server did not become healthy in time.'
    }

    Write-Host '[6/8] Running smoke-test transcript ingests...'
    $Result1 = Invoke-JsonPost 'http://127.0.0.1:8000/v1/ingest/transcript' (Join-Path $Root 'sample_payloads\transcript_1.json')
    $Result2 = Invoke-JsonPost 'http://127.0.0.1:8000/v1/ingest/transcript' (Join-Path $Root 'sample_payloads\transcript_2.json')

    $MergePreviewBody = @{
        left_package_id = $Result1.package_id
        right_package_id = $Result2.package_id
    } | ConvertTo-Json

    Write-Host '[7/8] Running merge preview...'
    $MergePreview = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/merge/preview' -ContentType 'application/json' -Body $MergePreviewBody

    $RetrieveBody = @{
        agent_id = 'alvin-savage'
        query = 'What is the project and what are the constraints?'
        top_k = 8
    } | ConvertTo-Json

    Write-Host '[8/8] Running retrieval test...'
    $Retrieve = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/retrieve/context' -ContentType 'application/json' -Body $RetrieveBody

    $Summary = @{
        transcript_1_package_id = $Result1.package_id
        transcript_2_package_id = $Result2.package_id
        merge_preview = $MergePreview.summary
        retrieval_preview = $Retrieve.text
        docs_url = 'http://127.0.0.1:8000/docs'
    } | ConvertTo-Json -Depth 8

    Set-Content -LiteralPath (Join-Path $Root 'automation-results.json') -Value $Summary -Encoding UTF8

    Write-Banner 'Bootstrap complete'
    Write-Host 'Docs:' -NoNewline
    Write-Host ' http://127.0.0.1:8000/docs' -ForegroundColor Yellow
    Write-Host 'Results file:' -NoNewline
    Write-Host " $(Join-Path $Root 'automation-results.json')" -ForegroundColor Yellow
    Write-Host 'Server is still running in the background.' -ForegroundColor Green
    Write-Host 'To stop it later, run:' -ForegroundColor Yellow
    Write-Host "  Stop-Process -Id $($Server.Id)"
}
catch {
    if ($Server -and -not $Server.HasExited) {
        Stop-Process -Id $Server.Id -Force
    }
    throw
}
