$ErrorActionPreference = 'Stop'

function Get-IslePython {
    $bundled = Join-Path $PSScriptRoot 'runtime\python\python.exe'
    $candidate = $bundled
    if (-not (Test-Path -LiteralPath $candidate)) {
        $found = Get-Command python -ErrorAction SilentlyContinue
        if (-not $found) { throw 'Python is missing. Run setup.ps1 or extract the complete portable ZIP.' }
        $candidate = $found.Source
    }
    $probe = & $candidate -c "import sys,struct; assert sys.version_info >= (3,10) and struct.calcsize('P') == 8; print('OK')" 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ x64 is required. Run setup.ps1.' }
    return $candidate
}

function Get-IsleDotnet {
    $candidate = Join-Path $PSScriptRoot 'runtime\dotnet\dotnet.exe'
    if (-not (Test-Path -LiteralPath $candidate)) {
        $found = Get-Command dotnet -ErrorAction SilentlyContinue
        if (-not $found) { throw '.NET runtime is missing. Run setup.ps1 or extract the complete portable ZIP.' }
        $candidate = $found.Source
    }
    $runtimes = & $candidate --list-runtimes
    if ($LASTEXITCODE -ne 0 -or -not ($runtimes -match '^Microsoft.NETCore.App 10\.') -or -not ($runtimes -match '^Microsoft.AspNetCore.App 10\.')) {
        throw '.NET 10 and ASP.NET Core 10 runtimes are required. Run setup.ps1.'
    }
    return $candidate
}

function Test-IsleDependencies {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'The portable package requires Windows x64.' }
    $pythonPath = Get-IslePython
    $dotnetPath = Get-IsleDotnet
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'decoder\bin\IsleDecoder.dll'))) {
        throw 'Replay decoder is missing. Run setup.ps1 or extract the complete portable ZIP.'
    }
    return @{ Python=$pythonPath; Dotnet=$dotnetPath }
}
