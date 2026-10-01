$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Host "WARNING: This deletes the local project database volume." -ForegroundColor Red
$answer = Read-Host "Type RESET to continue"
if ($answer -ne "RESET") { Write-Host "Cancelled."; exit 0 }
docker compose -f docker-compose.yml down -v --remove-orphans
Write-Host "Local project data was removed. Run START_PROJECT.bat for a clean start." -ForegroundColor Green
