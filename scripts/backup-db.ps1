param(
  [string]$OutputDirectory = "backups"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker is not installed or not available in PATH."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Docker Desktop is not running."
}

$service = "postgres"
$containerId = (docker compose ps -q $service).Trim()
if (-not $containerId) {
  throw "PostgreSQL container is not running. Start the project first."
}

$backupDir = Join-Path $Root $OutputDirectory
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$fileName = "automation_$stamp.dump"
$hostPath = Join-Path $backupDir $fileName
$containerPath = "/tmp/$fileName"

Write-Host "Creating PostgreSQL backup..." -ForegroundColor Cyan
docker compose exec -T $service sh -c "pg_dump -U automation -d automation -Fc -f '$containerPath'"
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed." }

docker compose cp "$($service):$containerPath" "$hostPath"
if ($LASTEXITCODE -ne 0) { throw "Failed to copy backup from the PostgreSQL container." }

docker compose exec -T $service rm -f "$containerPath" | Out-Null

Write-Host "Backup created:" -ForegroundColor Green
Write-Host $hostPath
