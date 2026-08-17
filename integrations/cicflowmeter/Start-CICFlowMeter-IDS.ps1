[CmdletBinding()]
param(
    [Uri]$Endpoint = "http://127.0.0.1:8000/api/flows",
    [switch]$Refresh
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($Endpoint.Scheme -ne "http" -or -not $Endpoint.AbsolutePath.EndsWith("/api/flows")) {
    throw "Endpoint must be an HTTP URL ending with /api/flows."
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$archivePath = Join-Path $PSScriptRoot "CICFlowMeter-IDS-Windows-1.0.0.zip"
$runtimeRoot = Join-Path $repositoryRoot "runtime-data\cicflowmeter-ids\1.0.0"
$applicationRoot = Join-Path $runtimeRoot "CICFlowMeter-4.0-ids1"
$applicationLauncher = Join-Path $applicationRoot "bin\CICFlowMeter.bat"

if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
    throw "Missing bundled CICFlowMeter archive: $archivePath"
}

$modelEndpoint = [UriBuilder]$Endpoint
$modelEndpoint.Path = $modelEndpoint.Path.Substring(
    0,
    $modelEndpoint.Path.Length - "/flows".Length
) + "/model"
try {
    $model = Invoke-RestMethod -Uri $modelEndpoint.Uri -Method Get -TimeoutSec 5
} catch {
    throw "The IDS backend is not ready at $($modelEndpoint.Uri). Start ids-serve first."
}
if ($model.expected_input_columns.Count -ne 75) {
    throw "The backend does not expose the expected 75-column CICFlowMeter contract."
}

if ($Refresh -and (Test-Path -LiteralPath $runtimeRoot)) {
    Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
}
if (-not (Test-Path -LiteralPath $applicationLauncher -PathType Leaf)) {
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    Expand-Archive -LiteralPath $archivePath -DestinationPath $runtimeRoot -Force
}
if (-not (Test-Path -LiteralPath $applicationLauncher -PathType Leaf)) {
    throw "The CICFlowMeter archive did not contain its expected Windows launcher."
}

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = [Security.Principal.WindowsPrincipal]::new($currentIdentity)
$isAdministrator = $currentPrincipal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdministrator) {
    Write-Warning "Npcap may require an Administrator PowerShell session to capture traffic."
}

$env:IDS_FLOW_ENDPOINT = $Endpoint.AbsoluteUri
$startArguments = @{
    FilePath = $applicationLauncher
    WorkingDirectory = Split-Path $applicationLauncher
    PassThru = $true
}
$process = Start-Process @startArguments

Write-Host "CICFlowMeter started with process ID $($process.Id)."
Write-Host "Completed flows will be sent to $($Endpoint.AbsoluteUri)"
