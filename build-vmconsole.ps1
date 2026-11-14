param([string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'setup.ps1')
. (Join-Path $PSScriptRoot 'runtime.ps1')
$pythonPath = Get-IslePython
$packagingArguments = @('--console-script')
if ($OutputDirectory) { $packagingArguments += @('--output-dir', $OutputDirectory) }
& $pythonPath (Join-Path $PSScriptRoot 'package_portable.py') @packagingArguments
if ($LASTEXITCODE -ne 0) { throw 'VMconsole packaging failed.' }
