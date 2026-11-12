param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ServiceArguments)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'runtime.ps1')
try { $resolved = Test-IsleDependencies }
catch {
    & (Join-Path $PSScriptRoot 'setup.ps1')
    $resolved = Test-IsleDependencies
}
$env:PYTHONUTF8 = '1'
& $resolved.Python -u (Join-Path $PSScriptRoot 'replay_service.py') @ServiceArguments
exit $LASTEXITCODE
