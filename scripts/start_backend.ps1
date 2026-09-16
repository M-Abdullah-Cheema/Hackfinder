# Start QuestHub local backend: Redis check + Celery worker + Celery Beat.
# Scrapes every SCRAPE_INTERVAL_SECONDS (default 10 hours).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $env:LOCALAPPDATA "ms-playwright"
if (-not $env:SCRAPE_INTERVAL_SECONDS) {
    $env:SCRAPE_INTERVAL_SECONDS = "36000"  # 10 hours
}

Write-Host "[QuestHub] Starting local scrape backend..." -ForegroundColor Cyan
Write-Host "  Interval: $($env:SCRAPE_INTERVAL_SECONDS)s" -ForegroundColor DarkGray

try {
    python -c "import redis; redis.from_url('redis://localhost:6379/0').ping(); print('REDIS_OK')"
} catch {
    Write-Host "[WARN] Redis not reachable on localhost:6379" -ForegroundColor Yellow
    Write-Host "  Start it with: docker start hackfinder-redis" -ForegroundColor Yellow
}

$state = Join-Path $Root "scrapers\auth_states\state.json"
if (-not (Test-Path $state) -or (Get-Item $state).Length -lt 10) {
    Write-Host "[WARN] Instagram session missing. Run: python scrapers\auth_states\login.py" -ForegroundColor Yellow
}

$workerArgs = @(
    "-m", "celery", "-A", "core.celery_app.celery_app", "worker",
    "-Q", "scrapers,ocr_tasks,ai_extraction,deliveries",
    "-l", "info", "-P", "solo",
    "-n", "questhub@$env:COMPUTERNAME"
)
$beatArgs = @(
    "-m", "celery", "-A", "core.celery_app.celery_app", "beat",
    "-l", "info"
)

Write-Host "[QuestHub] Launching Celery worker..." -ForegroundColor Green
Start-Process -FilePath "python" -ArgumentList $workerArgs -WorkingDirectory $Root -WindowStyle Minimized

Start-Sleep -Seconds 3

Write-Host "[QuestHub] Launching Celery Beat (auto-scrape)..." -ForegroundColor Green
Start-Process -FilePath "python" -ArgumentList $beatArgs -WorkingDirectory $Root -WindowStyle Minimized

Write-Host ""
Write-Host "[OK] Backend started. Vercel keeps serving last scraped data when this PC is off." -ForegroundColor Green
Write-Host "     Manual scrape: python scripts\trigger_pipeline.py"
