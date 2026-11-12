$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot 'web\assets\gateway.webp'
$expected = '4019299d2bf365ff8c8aa2063ad195317edc0d6da3ad39f4815c5d82c2b66611'
if ((Test-Path -LiteralPath $target) -and ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -eq $expected)) { return }
$temporary = $target + '.download'
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Write-Host 'Downloading Gateway basemap from VulnonaMAP...'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://vulnona.com/game/map/map/Gateway_v0.21.7/base/3.webp' -OutFile $temporary
    if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $expected) {
        throw 'Gateway image checksum changed. Check MAP-SOURCES.md before updating the pinned asset.'
    }
    Move-Item -LiteralPath $temporary -Destination $target -Force
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}
