$ErrorActionPreference = 'Stop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework 4.8 compiler is required to build the service executables.' }
$codeRoot = Join-Path $PSScriptRoot 'windows-service'
$common = Join-Path $codeRoot 'Common.cs'
$manifest = Join-Path $codeRoot 'app.manifest'
$refs = @('/r:System.Core.dll','/r:System.Web.Extensions.dll','/r:System.ServiceProcess.dll','/r:System.Windows.Forms.dll','/r:System.Drawing.dll')
& $compiler /nologo /target:winexe /platform:x64 /optimize+ (('/win32manifest:' + $manifest)) (('/out:' + (Join-Path $PSScriptRoot 'ReplayRadar.Service.exe'))) @refs $common (Join-Path $codeRoot 'ServiceHost.cs')
if ($LASTEXITCODE -ne 0) { throw 'Service host build failed.' }
& $compiler /nologo /target:winexe /platform:x64 /optimize+ (('/win32manifest:' + $manifest)) (('/out:' + (Join-Path $PSScriptRoot 'ReplayRadar.exe'))) @refs $common (Join-Path $codeRoot 'Manager.cs')
if ($LASTEXITCODE -ne 0) { throw 'Service manager build failed.' }
$config = '<configuration><startup><supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.8" /></startup></configuration>'
foreach ($name in @('ReplayRadar.exe.config','ReplayRadar.Service.exe.config')) { Set-Content -LiteralPath (Join-Path $PSScriptRoot $name) -Value $config -Encoding UTF8 }
Write-Host 'Built ReplayRadar.exe and ReplayRadar.Service.exe.'
