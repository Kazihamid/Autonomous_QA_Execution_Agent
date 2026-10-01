$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root 'services\control-plane\src\main\java\com\brac\automation\platform\recorder\RecorderWorkerClient.java'

if (-not (Test-Path $target)) {
    throw "RecorderWorkerClient.java not found at: $target`nPlace this patch in the project root (same folder as docker-compose.yml)."
}

$backup = "$target.bak-restclient-v021"
Copy-Item $target $backup -Force

$content = [System.IO.File]::ReadAllText($target)

# Remove a UTF-8 BOM character if a previous Windows PowerShell write inserted one.
$content = $content.TrimStart([char]0xFEFF)

$pattern = 'public\s+RecorderWorkerClient\s*\(\s*RestClient\.Builder\s+builder\s*,\s*@Value\("\$\{platform\.recorder\.base-url\}"\)\s+String\s+baseUrl\s*\)\s*\{\s*this\.client\s*=\s*builder\.baseUrl\(baseUrl\)\.build\(\);\s*\}'
$replacement = @'
public RecorderWorkerClient(@Value("${platform.recorder.base-url}") String baseUrl) {
        this.client = RestClient.builder().baseUrl(baseUrl).build();
    }
'@

if ([System.Text.RegularExpressions.Regex]::IsMatch($content, $pattern)) {
    $content = [System.Text.RegularExpressions.Regex]::Replace($content, $pattern, $replacement)
} elseif ($content -match 'RestClient\.builder\(\)\.baseUrl\(baseUrl\)\.build\(\)') {
    Write-Host 'RestClient constructor was already patched.' -ForegroundColor Yellow
} else {
    throw "Could not find either the original or already-patched RecorderWorkerClient constructor. Backup: $backup"
}

# IMPORTANT: write UTF-8 WITHOUT BOM so javac can compile the source file.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($target, $content, $utf8NoBom)

Write-Host 'RecorderWorkerClient fixed successfully.' -ForegroundColor Green
Write-Host ' - RestClient.Builder injection removed' -ForegroundColor Green
Write-Host ' - Source saved as UTF-8 without BOM' -ForegroundColor Green
Write-Host "Backup: $backup" -ForegroundColor DarkGray
