$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

$Source = Join-Path $Root "db\migrations\V004__vertical_slice_3_codegen.sql"
$TargetDir = Join-Path $Root "services\control-plane\src\main\resources\db\migration"
$Target = Join-Path $TargetDir "V004__vertical_slice_3_codegen.sql"

if (-not (Test-Path -LiteralPath $Source)) {
    throw "VS3 migration source file was not found: $Source"
}

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
Copy-Item -LiteralPath $Source -Destination $Target -Force

if (-not (Test-Path -LiteralPath $Target)) {
    throw "Failed to copy V004 migration into the Control Plane classpath."
}

Write-Host ""
Write-Host "VS3 Flyway migration patch applied successfully." -ForegroundColor Green
Write-Host "Source : $Source" -ForegroundColor DarkGray
Write-Host "Target : $Target" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Why this fix is needed:" -ForegroundColor Cyan
Write-Host "The VS3 upgrade placed V004 under db\migrations, but Spring Boot Flyway loads" -ForegroundColor Cyan
Write-Host "migrations from services\control-plane\src\main\resources\db\migration." -ForegroundColor Cyan
Write-Host ""
Write-Host "Database contents were NOT modified by this patch." -ForegroundColor Green
Write-Host "Rebuild/recreate the control-plane next so Flyway can apply V004." -ForegroundColor Yellow
