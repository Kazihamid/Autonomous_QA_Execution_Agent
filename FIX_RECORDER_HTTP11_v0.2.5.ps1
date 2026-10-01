$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$client = Join-Path $root 'services\control-plane\src\main\java\com\brac\automation\platform\recorder\RecorderWorkerClient.java'

if (-not (Test-Path $client)) {
    throw "RecorderWorkerClient.java not found at: $client`nPlace this patch in the project root (same folder as docker-compose.yml)."
}

$backup = "$client.bak-http11-v025"
Copy-Item $client $backup -Force

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$source = [System.IO.File]::ReadAllText($client).TrimStart([char]0xFEFF)

if ($source -notmatch 'java\.net\.http\.HttpClient') {
    throw "This patch expects the v0.2.4 JDK HttpClient implementation. Apply FIX_RECORDER_JDK_HTTP_v0.2.4.ps1 first."
}

# Force HTTP/1.1 at client level. Java HttpClient otherwise prefers HTTP/2 and
# attempts a clear-text h2c upgrade against http://recorder:8090.
if ($source -notmatch '\.version\(HttpClient\.Version\.HTTP_1_1\)') {
    $source = $source -replace '(this\.http\s*=\s*HttpClient\.newBuilder\(\)\s*\r?\n\s*)(\.connectTimeout)', '$1.version(HttpClient.Version.HTTP_1_1)' + "`r`n            " + '$2'
}

# Also force HTTP/1.1 on each request as a second safeguard.
$oldRequest = 'return HttpRequest\.newBuilder\(URI\.create\(baseUrl \+ path\)\)\s*\r?\n\s*\.timeout\(Duration\.ofSeconds\(60\)\)'
if ($source -match $oldRequest -and $source -notmatch 'HttpRequest\.newBuilder\(URI\.create\(baseUrl \+ path\)\)\s*\r?\n\s*\.version\(HttpClient\.Version\.HTTP_1_1\)') {
    $source = [regex]::Replace(
        $source,
        $oldRequest,
        "return HttpRequest.newBuilder(URI.create(baseUrl + path))`r`n            .version(HttpClient.Version.HTTP_1_1)`r`n            .timeout(Duration.ofSeconds(60))"
    )
}

[System.IO.File]::WriteAllText($client, $source, $utf8NoBom)

Write-Host ''
Write-Host 'Recorder transport patch v0.2.5 applied successfully.' -ForegroundColor Green
Write-Host ' - Forced Java HttpClient to HTTP/1.1' -ForegroundColor Green
Write-Host ' - Disabled clear-text HTTP/2 (h2c) upgrade attempts for Recorder traffic' -ForegroundColor Green
Write-Host ' - Applied HTTP/1.1 at both client and request level' -ForegroundColor Green
Write-Host ' - Database/data untouched' -ForegroundColor Green
Write-Host "Backup: $backup" -ForegroundColor DarkGray
