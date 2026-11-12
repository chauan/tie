param([ValidateSet('Start','Stop','Status')][string]$Action = 'Start', [ValidateRange(1024,65535)][int]$Port=8765)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$scriptFile = Join-Path $projectRoot 'replay_service.py'
$dataRoot = Join-Path $projectRoot 'data'
$pidFile = Join-Path $dataRoot $(if ($Port -eq 8765) { 'service.pid' } else { "service-$Port.pid" })
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
$ownedProcess = $null
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    if ($health.application -eq 'isle-replay-radar' -and $health.service_root -eq $projectRoot -and $health.pid -gt 0) {
        $ownedProcess = Get-Process -Id $health.pid -ErrorAction SilentlyContinue
    }
} catch { }
if ($Action -eq 'Stop') {
    if ($ownedProcess) { Stop-Process -Id $ownedProcess.Id; Write-Host 'Replay Radar stopped.' }
    else { Write-Host 'No matching background Replay Radar process.' }
    Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
    exit
}
if ($ownedProcess) { Write-Host "Replay Radar running: http://127.0.0.1:$Port (PID $($ownedProcess.Id))"; exit }
if ($Action -eq 'Status') { Write-Host 'Replay Radar is not running in background.'; exit }
$probe = New-Object System.Net.Sockets.TcpClient
try {
    if ($probe.ConnectAsync('127.0.0.1', $Port).Wait(1000) -and $probe.Connected) {
        throw "Port $Port is already in use; existing application was left running."
    }
} catch [System.Management.Automation.MethodInvocationException] {
    # Connection refused: the port is available.
} finally { $probe.Dispose() }
. (Join-Path $projectRoot 'runtime.ps1')
try { $resolved = Test-IsleDependencies }
catch { & (Join-Path $projectRoot 'setup.ps1'); $resolved = Test-IsleDependencies }
$pythonExe = $resolved.Python
$env:PYTHONUTF8 = '1'
$launched = Start-Process -FilePath $pythonExe -ArgumentList @('-u', ('"' + $scriptFile + '"'), '--port', $Port) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataRoot "stdout-$Port.log") -RedirectStandardError (Join-Path $dataRoot "stderr-$Port.log")
Set-Content -LiteralPath $pidFile -Value $launched.Id -Encoding ASCII
for ($attempt=0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 200
    try {
        $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 1
        if ($ready.application -eq 'isle-replay-radar' -and $ready.service_root -eq $projectRoot -and $ready.pid -eq $launched.Id) {
            Write-Host "Replay Radar started: http://127.0.0.1:$Port (PID $($launched.Id))"; exit
        }
    } catch { }
    $launched.Refresh()
    if ($launched.HasExited) { throw "Service exited. Check data\stderr-$Port.log." }
}
throw "Service did not become ready. Check data\stderr-$Port.log."
