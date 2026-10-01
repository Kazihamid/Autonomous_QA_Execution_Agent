$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Host ""; Write-Host "Autonomous QA Execution Agent v0.3.2 - Easy Start" -ForegroundColor Cyan; Write-Host "================================================" -ForegroundColor Cyan
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Write-Host "Docker was not found." -ForegroundColor Red; exit 1 }
try { docker info *> $null } catch { Write-Host "Docker Desktop is installed but is not running." -ForegroundColor Red; exit 1 }
Write-Host "[1/6] Building and starting PostgreSQL, Recorder, Code Generator, Runner, Control Plane, and Web UI..." -ForegroundColor Green
docker compose -f docker-compose.yml up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed." }
function Wait-Health($Name,$Url,$Service){ Write-Host "Waiting for $Name..." -ForegroundColor Green; for($i=0;$i -lt 150;$i++){try{$r=Invoke-RestMethod -Uri $Url -TimeoutSec 2;if($r.status -eq "UP"){return}}catch{};Start-Sleep -Seconds 2};Write-Host "$Name did not become healthy." -ForegroundColor Red;docker compose -f docker-compose.yml logs --tail=120 $Service;exit 1 }
Write-Host "[2/6] Recorder Worker" -ForegroundColor Green; Wait-Health "Recorder Worker" "http://localhost:8090/health" "recorder"
Write-Host "[3/6] Code Generator" -ForegroundColor Green; Wait-Health "Code Generator" "http://localhost:8100/health" "code-generator"
Write-Host "[4/6] Local Runner" -ForegroundColor Green; Wait-Health "Local Runner" "http://localhost:8110/health" "runner"
Write-Host "[5/6] Control Plane" -ForegroundColor Green; Wait-Health "Control Plane" "http://localhost:8080/api/v1/health" "control-plane"
Write-Host "[6/6] Checking Web UI..." -ForegroundColor Green
$webReady=$false;for($i=0;$i -lt 60;$i++){try{$r=Invoke-WebRequest -Uri "http://localhost:3000/login" -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){$webReady=$true;break}}catch{};Start-Sleep -Seconds 2};if(-not $webReady){docker compose logs --tail=120 web;exit 1}
Write-Host "";Write-Host "PROJECT IS RUNNING" -ForegroundColor Green
Write-Host "Web UI:          http://localhost:3000/login";Write-Host "Backend API:     http://localhost:8080/api/v1/health";Write-Host "Recorder API:    http://localhost:8090/health";Write-Host "Code Generator:  http://localhost:8100/health";Write-Host "Local Runner:    http://localhost:8110/health";Write-Host "Managed Browser: http://localhost:6080/vnc.html?autoconnect=1&resize=scale";Write-Host "PostgreSQL:      localhost:5432"
Start-Process "http://localhost:3000/login"

