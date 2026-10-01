$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
docker compose -f docker-compose.yml logs -f --tail=150
