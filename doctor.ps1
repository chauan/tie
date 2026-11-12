param()
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'runtime.ps1')
    $resolved = Test-IsleDependencies
    & $resolved.Python -c "import sys, http.server, gzip, threading, pathlib; print('Python OK:',sys.version.split()[0]); print('Python path:',sys.executable)"
    if ($LASTEXITCODE -ne 0) { throw 'Python standard library is incomplete.' }
    & $resolved.Dotnet --list-runtimes
    if ($LASTEXITCODE -ne 0) { throw '.NET cannot start.' }
    Write-Host 'Decoder OK. Dependencies are ready. Open start.cmd.'
    Write-Host 'The game replay folder and SteamID are configured on the web page.'
} catch { Write-Host ('CHECK FAILED: ' + $_.Exception.Message) -ForegroundColor Red; exit 1 }
