$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$client = Join-Path $root 'services\control-plane\src\main\java\com\brac\automation\platform\recorder\RecorderWorkerClient.java'
$pom = Join-Path $root 'services\control-plane\pom.xml'

if (-not (Test-Path $client)) {
    throw "RecorderWorkerClient.java not found at: $client`nPlace this patch in the project root (same folder as docker-compose.yml)."
}
if (-not (Test-Path $pom)) {
    throw "pom.xml not found at: $pom"
}

$pomBackup = "$pom.bak-recorder-json-v023"
Copy-Item $pom $pomBackup -Force

$backup = "$client.bak-recorder-json-v023"
Copy-Item $client $backup -Force

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$java = [System.IO.File]::ReadAllText($client).TrimStart([char]0xFEFF)


# Ensure Boot's blocking REST client starter is present for response conversion.
$pomText = [System.IO.File]::ReadAllText($pom).TrimStart([char]0xFEFF)
if ($pomText -notmatch '<artifactId>spring-boot-starter-restclient</artifactId>') {
    $webDependencyPattern = '<dependency>\s*<groupId>org\.springframework\.boot</groupId>\s*<artifactId>spring-boot-starter-web</artifactId>\s*</dependency>'
    $match = [regex]::Match($pomText, $webDependencyPattern)
    if (-not $match.Success) {
        throw "Could not find spring-boot-starter-web in pom.xml."
    }
    $restClientDependency = "`r`n    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-restclient</artifactId></dependency>"
    $pomText = $pomText.Insert($match.Index + $match.Length, $restClientDependency)
}
[System.IO.File]::WriteAllText($pom, $pomText, $utf8NoBom)

if ($java -notmatch 'import tools\.jackson\.databind\.ObjectMapper;') {
    $java = $java -replace 'import tools\.jackson\.databind\.JsonNode;', "import tools.jackson.databind.JsonNode;`r`nimport tools.jackson.databind.ObjectMapper;"
}

if ($java -notmatch 'private final ObjectMapper mapper;') {
    $java = $java -replace 'private final RestClient client;', "private final RestClient client;`r`n    private final ObjectMapper mapper;"
}

$constructorInjected = 'public\s+RecorderWorkerClient\s*\(\s*RestClient\.Builder\s+builder\s*,\s*@Value\("\$\{platform\.recorder\.base-url\}"\)\s+String\s+baseUrl\s*\)\s*\{\s*this\.client\s*=\s*builder\.baseUrl\(baseUrl\)\.build\(\);\s*\}'
$constructorDirect = 'public\s+RecorderWorkerClient\s*\(\s*@Value\("\$\{platform\.recorder\.base-url\}"\)\s+String\s+baseUrl\s*\)\s*\{\s*this\.client\s*=\s*RestClient\.builder\(\)\.baseUrl\(baseUrl\)\.build\(\);\s*\}'
$constructorAlready = 'public\s+RecorderWorkerClient\s*\(\s*RestClient\.Builder\s+builder\s*,\s*ObjectMapper\s+mapper\s*,\s*@Value\("\$\{platform\.recorder\.base-url\}"\)\s+String\s+baseUrl\s*\)'

$replacement = @'
public RecorderWorkerClient(RestClient.Builder builder, ObjectMapper mapper, @Value("${platform.recorder.base-url}") String baseUrl) {
        this.client = builder.baseUrl(baseUrl).build();
        this.mapper = mapper;
    }
'@

if ([regex]::IsMatch($java, $constructorInjected)) {
    $java = [regex]::Replace($java, $constructorInjected, $replacement)
} elseif ([regex]::IsMatch($java, $constructorDirect)) {
    $java = [regex]::Replace($java, $constructorDirect, $replacement)
} elseif (-not [regex]::IsMatch($java, $constructorAlready)) {
    throw "Could not recognize RecorderWorkerClient constructor. Backup created at: $backup"
}

$java = $java.Replace('.body(new CreateRequest(startUrl, browser.toLowerCase(), false, scenarioName))',
                      '.body(json(new CreateRequest(startUrl, browser.toLowerCase(), false, scenarioName)))')
$java = $java.Replace('.body(new AssertionRequest(selector, assertionType, expected))',
                      '.body(json(new AssertionRequest(selector, assertionType, expected)))')
$java = $java.Replace('.body(new CheckpointRequest(description))',
                      '.body(json(new CheckpointRequest(description)))')

if ($java -notmatch 'private String json\(Object value\)') {
    $marker = '    public record CreateRequest('
    $idx = $java.IndexOf($marker)
    if ($idx -lt 0) {
        throw "Could not find record definitions in RecorderWorkerClient.java. Backup created at: $backup"
    }

    $helper = @'
    private String json(Object value) {
        return mapper.writeValueAsString(value);
    }

'@
    $java = $java.Insert($idx, $helper)
}

[System.IO.File]::WriteAllText($client, $java, $utf8NoBom)

Write-Host ''
Write-Host 'Recorder JSON-body patch v0.2.3 applied successfully.' -ForegroundColor Green
Write-Host ' - ObjectMapper injected' -ForegroundColor Green
Write-Host ' - create-session request serialized to an explicit JSON string' -ForegroundColor Green
Write-Host ' - assertion/checkpoint requests serialized the same way' -ForegroundColor Green
Write-Host ' - UTF-8 without BOM' -ForegroundColor Green
Write-Host "Backups:`n  $backup`n  $pomBackup" -ForegroundColor DarkGray
