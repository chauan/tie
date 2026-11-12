param()
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'setup.ps1')
. (Join-Path $PSScriptRoot 'runtime.ps1')
$pythonPath = Get-IslePython
& $pythonPath (Join-Path $PSScriptRoot 'package_portable.py')
if ($LASTEXITCODE -ne 0) { throw 'Portable packaging failed.' }
