$ErrorActionPreference = 'Stop'
$pythonRoot = Join-Path $PSScriptRoot 'runtime\python'
if (Test-Path -LiteralPath (Join-Path $pythonRoot 'python.exe')) { return }
$cacheRoot = Join-Path $PSScriptRoot 'runtime\downloads'
New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
$archive = Join-Path $cacheRoot 'python-3.14.10-embed-amd64.zip'
$expected = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'
if (-not (Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip' -OutFile ($archive + '.part')
    if ((Get-FileHash -LiteralPath ($archive + '.part') -Algorithm SHA256).Hash -ne $expected) { throw 'Python checksum mismatch; download was not used.' }
    Move-Item -LiteralPath ($archive + '.part') -Destination $archive -Force
}
Expand-Archive -LiteralPath $archive -DestinationPath $pythonRoot -Force
