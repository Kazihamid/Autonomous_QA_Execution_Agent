$ErrorActionPreference = 'Stop'

Write-Host "Autonomous QA Execution Agent - Spring Boot 4 Flyway Fix" -ForegroundColor Cyan
Write-Host "Project root: $PSScriptRoot"

$pom = Join-Path $PSScriptRoot 'services\control-plane\pom.xml'
$compose = Join-Path $PSScriptRoot 'docker-compose.yml'

if (-not (Test-Path $pom)) {
    throw "Could not find services\control-plane\pom.xml. Put this script in the project root (same folder as docker-compose.yml) and run it there."
}

$pomText = Get-Content $pom -Raw
$oldFlyway = '<dependency><groupId>org.flywaydb</groupId><artifactId>flyway-core</artifactId></dependency>'
$newFlyway = '<dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-flyway</artifactId></dependency>'

if ($pomText.Contains($newFlyway)) {
    Write-Host "Flyway starter is already configured." -ForegroundColor Green
} elseif ($pomText.Contains($oldFlyway)) {
    Copy-Item $pom "$pom.bak" -Force
    $pomText = $pomText.Replace($oldFlyway, $newFlyway)
    Set-Content -Path $pom -Value $pomText -Encoding UTF8
    Write-Host "Updated pom.xml: flyway-core -> spring-boot-starter-flyway" -ForegroundColor Green
    Write-Host "Backup created: $pom.bak" -ForegroundColor DarkGray
} else {
    throw "Expected Flyway dependency was not found in pom.xml. No changes were made."
}

# PostgreSQL 18 uses /var/lib/postgresql as the recommended volume mount root.
if (Test-Path $compose) {
    $composeText = Get-Content $compose -Raw
    if ($composeText.Contains('postgres-data:/var/lib/postgresql/data')) {
        Copy-Item $compose "$compose.bak" -Force
        $composeText = $composeText.Replace('postgres-data:/var/lib/postgresql/data', 'postgres-data:/var/lib/postgresql')
        Set-Content -Path $compose -Value $composeText -Encoding UTF8
        Write-Host "Updated PostgreSQL 18 volume mount path." -ForegroundColor Green
        Write-Host "Backup created: $compose.bak" -ForegroundColor DarkGray
    } else {
        Write-Host "PostgreSQL volume path is already updated." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Patch complete." -ForegroundColor Cyan
Write-Host "Next commands:" -ForegroundColor Yellow
Write-Host "  docker compose down -v"
Write-Host "  docker compose build --no-cache control-plane"
Write-Host "  docker compose up"

