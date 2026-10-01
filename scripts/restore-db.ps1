param(
  [Parameter(Mandatory = $true)]
  [string]$BackupFile
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$resolved = Resolve-Path $BackupFile -ErrorAction Stop
$backupPath = $resolved.Path

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

Write-Host "WARNING: Restoring will replace conflicting objects in the local automation database." -ForegroundColor Yellow
Write-Host "Backup: $backupPath"
$answer = Read-Host "Type RESTORE to continue"
if ($answer -ne "RESTORE") {
  Write-Host "Cancelled."
  exit 0
}

$fileName = [IO.Path]::GetFileName($backupPath)
$containerPath = "/tmp/$fileName"

docker compose cp "$backupPath" "$($service):$containerPath"
if ($LASTEXITCODE -ne 0) { throw "Failed to copy backup into the PostgreSQL container." }

Write-Host "Restoring PostgreSQL backup..." -ForegroundColor Cyan
docker compose exec -T $service pg_restore -U automation -d automation --clean --if-exists --no-owner "$containerPath"
$restoreExit = $LASTEXITCODE

docker compose exec -T $service rm -f "$containerPath" | Out-Null

if ($restoreExit -ne 0) {
  throw "pg_restore failed with exit code $restoreExit."
}

Write-Host "Database restore completed successfully." -ForegroundColor Green
