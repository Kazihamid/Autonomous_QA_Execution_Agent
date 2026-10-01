$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root 'services\control-plane\src\main\java\com\brac\automation\platform\recorder\RecorderWorkerClient.java'

if (-not (Test-Path $target)) {
    throw "RecorderWorkerClient.java not found at: $target`nPlace this patch in the project root (same folder as docker-compose.yml) and run it again."
}

$backup = "$target.bak-restclient"
Copy-Item $target $backup -Force

$content = Get-Content $target -Raw
$old = 'public RecorderWorkerClient(RestClient.Builder builder, @Value("${platform.recorder.base-url}") String baseUrl) {' + "`r`n" + '        this.client = builder.baseUrl(baseUrl).build();' + "`r`n" + '    }'
$new = 'public RecorderWorkerClient(@Value("${platform.recorder.base-url}") String baseUrl) {' + "`r`n" + '        this.client = RestClient.builder().baseUrl(baseUrl).build();' + "`r`n" + '    }'

if (-not $content.Contains($old)) {
    $oldLf = 'public RecorderWorkerClient(RestClient.Builder builder, @Value("${platform.recorder.base-url}") String baseUrl) {' + "`n" + '        this.client = builder.baseUrl(baseUrl).build();' + "`n" + '    }'
    $newLf = 'public RecorderWorkerClient(@Value("${platform.recorder.base-url}") String baseUrl) {' + "`n" + '        this.client = RestClient.builder().baseUrl(baseUrl).build();' + "`n" + '    }'
    if ($content.Contains($oldLf)) {
        $content = $content.Replace($oldLf, $newLf)
    } elseif ($content.Contains('RestClient.builder().baseUrl(baseUrl).build()')) {
        Write-Host 'Patch already applied. No changes needed.' -ForegroundColor Yellow
        exit 0
    } else {
        throw "Expected constructor pattern was not found. Backup created at: $backup"
    }
} else {
    $content = $content.Replace($old, $new)
}

Set-Content -Path $target -Value $content -Encoding UTF8

Write-Host 'Patched RecorderWorkerClient successfully.' -ForegroundColor Green
Write-Host 'Changed RestClient.Builder constructor injection to RestClient.builder().' -ForegroundColor Green
Write-Host "Backup: $backup" -ForegroundColor DarkGray
