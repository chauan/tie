param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
& (Join-Path $projectRoot 'bootstrap-map.ps1')
& (Join-Path $projectRoot 'bootstrap-python.ps1')
. (Join-Path $projectRoot 'runtime.ps1')
if (-not $Rebuild) {
    try { $null = Test-IsleDependencies; Write-Host 'Ready. Run VMconsole.cmd and open http://127.0.0.1:8765'; return }
    catch { }
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'decoder\IsleDecoder.csproj'))) {
    throw 'Portable package is incomplete. Extract the complete ZIP again; building requires the source project.'
}
$runtimeRoot = Join-Path $projectRoot 'runtime'
$dotnetExe = Join-Path $runtimeRoot 'dotnet\dotnet.exe'
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$sdkPresent = $false
if (Test-Path -LiteralPath $dotnetExe) { $sdkPresent = [bool](& $dotnetExe --list-sdks) }
if (-not $sdkPresent) {
    $installer = Join-Path $runtimeRoot 'dotnet-install.ps1'
    Invoke-WebRequest -Uri 'https://dot.net/v1/dotnet-install.ps1' -OutFile $installer
    & $installer -Channel 10.0 -InstallDir (Join-Path $runtimeRoot 'dotnet') -NoPath
    if ($LASTEXITCODE -ne 0) { throw '.NET installation failed.' }
}
$env:DOTNET_CLI_HOME = Join-Path $runtimeRoot 'cli'
$env:APPDATA = Join-Path $runtimeRoot 'appdata'
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_GENERATE_ASPNET_CERTIFICATE = 'false'
New-Item -ItemType Directory -Path $env:APPDATA -Force | Out-Null
$projectFile = Join-Path $projectRoot 'decoder\IsleDecoder.csproj'
& $dotnetExe restore $projectFile --configfile (Join-Path $projectRoot 'NuGet.Config')
if ($LASTEXITCODE -ne 0) { throw 'Decoder restore failed.' }
& $dotnetExe build $projectFile -c Release -o (Join-Path $projectRoot 'decoder\bin') --no-restore --nologo
if ($LASTEXITCODE -ne 0) { throw 'Decoder build failed.' }
Write-Host 'Ready. Run VMconsole.cmd and open http://127.0.0.1:8765'
