$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$client = Join-Path $root 'services\control-plane\src\main\java\com\brac\automation\platform\recorder\RecorderWorkerClient.java'

if (-not (Test-Path $client)) {
    throw "RecorderWorkerClient.java not found at: $client`nPlace this patch in the project root (same folder as docker-compose.yml)."
}

$backup = "$client.bak-http11-v0251"
Copy-Item $client $backup -Force

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$source = [System.IO.File]::ReadAllText($client).TrimStart([char]0xFEFF)

if ($source -notmatch 'java\.net\.http\.HttpClient') {
    throw "This patch expects the v0.2.4 JDK HttpClient implementation. Apply FIX_RECORDER_JDK_HTTP_v0.2.4.ps1 first."
}

$changed = $false

# 1) Force HTTP/1.1 on the shared HttpClient builder.
if ($source -notmatch 'HttpClient\.newBuilder\(\)\s*\r?\n\s*\.version\(HttpClient\.Version\.HTTP_1_1\)') {
    $pattern = 'HttpClient\.newBuilder\(\)\s*\r?\n\s*\.connectTimeout'
    if ([regex]::IsMatch($source, $pattern)) {
        $source = [regex]::Replace(
            $source,
            $pattern,
            "HttpClient.newBuilder()`r`n            .version(HttpClient.Version.HTTP_1_1)`r`n            .connectTimeout",
            1
        )
        $changed = $true
    }
}

# 2) Force HTTP/1.1 on request builders too.
if ($source -notmatch 'HttpRequest\.newBuilder\(URI\.create\(baseUrl \+ path\)\)\s*\r?\n\s*\.version\(HttpClient\.Version\.HTTP_1_1\)') {
    $pattern2 = 'HttpRequest\.newBuilder\(URI\.create\(baseUrl \+ path\)\)\s*\r?\n\s*\.timeout'
    if ([regex]::IsMatch($source, $pattern2)) {
        $source = [regex]::Replace(
            $source,
            $pattern2,
            "HttpRequest.newBuilder(URI.create(baseUrl + path))`r`n            .version(HttpClient.Version.HTTP_1_1)`r`n            .timeout",
            1
        )
        $changed = $true
    }
}

if (-not $changed) {
    if ($source -match 'HTTP_1_1') {
        Write-Host 'HTTP/1.1 settings already present. No source changes were required.' -ForegroundColor Yellow
    } else {
        throw "Could not find the expected HttpClient/HttpRequest builder patterns. Backup created at: $backup"
    }
}

[System.IO.File]::WriteAllText($client, $source, $utf8NoBom)

Write-Host ''
Write-Host 'Recorder transport patch v0.2.5.1 applied successfully.' -ForegroundColor Green
Write-Host ' - Java HttpClient forced to HTTP/1.1' -ForegroundColor Green
Write-Host ' - Recorder requests forced to HTTP/1.1' -ForegroundColor Green
Write-Host ' - UTF-8 without BOM' -ForegroundColor Green
Write-Host ' - Database/data untouched' -ForegroundColor Green
Write-Host "Backup: $backup" -ForegroundColor DarkGray
