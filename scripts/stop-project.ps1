$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Host "Stopping Autonomous QA Execution Agent..." -ForegroundColor Yellow
docker compose -f docker-compose.yml down
Write-Host "Stopped. Your PostgreSQL data volume was preserved." -ForegroundColor Green

