$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pom = Join-Path $root 'services\control-plane\pom.xml'
$client = Join-Path $root 'services\control-plane\src\main\java\com\brac\automation\platform\recorder\RecorderWorkerClient.java'

if (-not (Test-Path $pom)) {
    throw "pom.xml not found at: $pom`nPlace this patch in the project root (same folder as docker-compose.yml)."
}
if (-not (Test-Path $client)) {
    throw "RecorderWorkerClient.java not found at: $client`nPlace this patch in the project root (same folder as docker-compose.yml)."
}

$pomBackup = "$pom.bak-restclient-v022"
$clientBackup = "$client.bak-restclient-v022"
Copy-Item $pom $pomBackup -Force
Copy-Item $client $clientBackup -Force

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# -----------------------------------------------------------------------------
# 1) Spring Boot 4 separates blocking REST-client auto-configuration into the
#    spring-boot-starter-restclient starter. Add it so Boot provides a
#    pre-configured RestClient.Builder with JSON HttpMessageConverters.
# -----------------------------------------------------------------------------
$pomText = [System.IO.File]::ReadAllText($pom).TrimStart([char]0xFEFF)

if ($pomText -notmatch '<artifactId>spring-boot-starter-restclient</artifactId>') {
    $webDependencyPattern = '<dependency>\s*<groupId>org\.springframework\.boot</groupId>\s*<artifactId>spring-boot-starter-web</artifactId>\s*</dependency>'
    $match = [System.Text.RegularExpressions.Regex]::Match($pomText, $webDependencyPattern)
    if (-not $match.Success) {
        throw "Could not find spring-boot-starter-web in pom.xml. Backups were created; no source changes have been written."
    }

    $restClientDependency = "`n    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-restclient</artifactId></dependency>"
    $insertAt = $match.Index + $match.Length
    $pomText = $pomText.Insert($insertAt, $restClientDependency)
    Write-Host 'Added spring-boot-starter-restclient to pom.xml.' -ForegroundColor Green
} else {
    Write-Host 'spring-boot-starter-restclient is already present in pom.xml.' -ForegroundColor Yellow
}

[System.IO.File]::WriteAllText($pom, $pomText, $utf8NoBom)

# -----------------------------------------------------------------------------
# 2) Restore injection of Boot's auto-configured RestClient.Builder.
#    The previous emergency patch used RestClient.builder() directly, which
#    bypassed Boot's configured JSON message converters in this project.
# -----------------------------------------------------------------------------
$javaText = [System.IO.File]::ReadAllText($client).TrimStart([char]0xFEFF)

$directBuilderPattern = 'public\s+RecorderWorkerClient\s*\(\s*@Value\("\$\{platform\.recorder\.base-url\}"\)\s+String\s+baseUrl\s*\)\s*\{\s*this\.client\s*=\s*RestClient\.builder\(\)\.baseUrl\(baseUrl\)\.build\(\);\s*\}'
$injectedBuilderPattern = 'public\s+RecorderWorkerClient\s*\(\s*RestClient\.Builder\s+builder\s*,\s*@Value\("\$\{platform\.recorder\.base-url\}"\)\s+String\s+baseUrl\s*\)\s*\{\s*this\.client\s*=\s*builder\.baseUrl\(baseUrl\)\.build\(\);\s*\}'

$replacement = @'
public RecorderWorkerClient(RestClient.Builder builder, @Value("${platform.recorder.base-url}") String baseUrl) {
        this.client = builder.baseUrl(baseUrl).build();
    }
'@

if ([System.Text.RegularExpressions.Regex]::IsMatch($javaText, $directBuilderPattern)) {
    $javaText = [System.Text.RegularExpressions.Regex]::Replace($javaText, $directBuilderPattern, $replacement)
    Write-Host 'Restored Boot-managed RestClient.Builder injection.' -ForegroundColor Green
} elseif ([System.Text.RegularExpressions.Regex]::IsMatch($javaText, $injectedBuilderPattern)) {
    Write-Host 'RecorderWorkerClient already uses injected RestClient.Builder.' -ForegroundColor Yellow
} else {
    throw "Could not recognize the RecorderWorkerClient constructor. Backups: $pomBackup and $clientBackup"
}

[System.IO.File]::WriteAllText($client, $javaText, $utf8NoBom)

Write-Host ''
Write-Host 'Recorder HTTP client fix applied successfully.' -ForegroundColor Green
Write-Host ' - Spring Boot REST-client starter enabled' -ForegroundColor Green
Write-Host ' - Boot-configured RestClient.Builder restored' -ForegroundColor Green
Write-Host ' - JSON request-body converters will be available' -ForegroundColor Green
Write-Host ' - Files saved UTF-8 without BOM' -ForegroundColor Green
Write-Host "Backups:`n  $pomBackup`n  $clientBackup" -ForegroundColor DarkGray
