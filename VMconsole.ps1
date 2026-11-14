param(
    [string]$SourceFolder,
    [string]$ReplayFile,
    [string]$CopyFolder,
    [string]$DataDirectory,
    [ValidateRange(1024,65535)][int]$Port=8765,
    [switch]$Configure,
    [switch]$NonInteractive
)
$ErrorActionPreference = 'Stop'
try { $host.UI.RawUI.WindowTitle = 'VMconsole' } catch { }
try { [Console]::OutputEncoding = New-Object Text.UTF8Encoding($false); $OutputEncoding = [Console]::OutputEncoding } catch { }
$env:PYTHONUTF8 = '1'
. (Join-Path $PSScriptRoot 'runtime.ps1')

try {
    $resolved = Test-IsleDependencies
    if (-not $DataDirectory) {
        $preferences = Join-Path $PSScriptRoot 'VMconsole.settings.json'
        if (Test-Path -LiteralPath $preferences) { $DataDirectory = (Get-Content -Raw -Encoding UTF8 -LiteralPath $preferences | ConvertFrom-Json).data_dir }
    }
    if (-not $DataDirectory) { $DataDirectory = Join-Path $PSScriptRoot 'data' }
    $DataDirectory = [IO.Path]::GetFullPath($DataDirectory)
    $active = $null
    try { $active = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 } catch { }
    if ($active) { throw "Port $Port is already running. Stop the previous instance before starting VMconsole." }
    [IO.Directory]::CreateDirectory($DataDirectory) | Out-Null
    $configFile = Join-Path $DataDirectory 'config.json'
    $config = @{}
    if (Test-Path -LiteralPath $configFile) {
        $saved = Get-Content -Raw -Encoding UTF8 -LiteralPath $configFile | ConvertFrom-Json
        foreach ($property in $saved.PSObject.Properties) { $config[$property.Name] = $property.Value }
    }
    $sourceWasProvided = [bool]$SourceFolder -or [bool]$ReplayFile
    if (-not $SourceFolder) { $SourceFolder = $config.source_dir }
    if (-not $SourceFolder) { $SourceFolder = Join-Path $env:LOCALAPPDATA 'TheIsle\Saved\Demos' }
    if (-not $PSBoundParameters.ContainsKey('ReplayFile')) { $ReplayFile = $config.filename }
    if ($ReplayFile -and [IO.Path]::IsPathRooted($ReplayFile)) { $SourceFolder = [IO.Path]::GetDirectoryName($ReplayFile); $ReplayFile = [IO.Path]::GetFileName($ReplayFile) }
    if (-not $CopyFolder) { $CopyFolder = $config.copy_dir }
    if (-not $CopyFolder) { $CopyFolder = Join-Path $DataDirectory 'snapshots' }
    if (($Configure -or (-not (Test-Path -LiteralPath $configFile) -and -not $sourceWasProvided)) -and -not $NonInteractive) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        try {
            $dialog.Description = 'Chon folder chua file .replay'
            $dialog.SelectedPath = $SourceFolder
            if ($dialog.ShowDialog() -ne [Windows.Forms.DialogResult]::OK) { exit 0 }
            $SourceFolder = $dialog.SelectedPath
            $fileDialog = New-Object System.Windows.Forms.OpenFileDialog
            try {
                $fileDialog.Title = 'Chon file .replay (Cancel = tu chon moi nhat)'
                $fileDialog.Filter = 'Replay (*.replay)|*.replay'
                $fileDialog.InitialDirectory = $SourceFolder
                if ($fileDialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK) { $SourceFolder = [IO.Path]::GetDirectoryName($fileDialog.FileName); $ReplayFile = [IO.Path]::GetFileName($fileDialog.FileName) } else { $ReplayFile = '' }
            } finally { $fileDialog.Dispose() }
            $dialog.Description = 'Chon folder ban sao rieng de quet'
            $dialog.SelectedPath = $CopyFolder
            if ($dialog.ShowDialog() -ne [Windows.Forms.DialogResult]::OK) { exit 0 }
            $CopyFolder = $dialog.SelectedPath
        } finally { $dialog.Dispose() }
    }
    $SourceFolder = [IO.Path]::GetFullPath($SourceFolder).TrimEnd('\')
    $CopyFolder = [IO.Path]::GetFullPath($CopyFolder).TrimEnd('\')
    if (-not [IO.Directory]::Exists($SourceFolder)) { throw 'Replay folder does not exist. Use -Configure to choose it.' }
    if ($ReplayFile -and ([IO.Path]::GetFileName($ReplayFile) -ne $ReplayFile -or -not $ReplayFile.EndsWith('.replay',[StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists((Join-Path $SourceFolder $ReplayFile)))) { throw 'Choose an existing .replay file in the source folder.' }
    $originPrefix = $SourceFolder + '\'; $copyPrefix = $CopyFolder + '\'
    if ($originPrefix.StartsWith($copyPrefix,[StringComparison]::OrdinalIgnoreCase) -or $copyPrefix.StartsWith($originPrefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'The source and copy folders must be separate.' }
    $config['source_dir'] = $SourceFolder; $config['filename'] = [string]$ReplayFile; $config['copy_dir'] = $CopyFolder
    if (-not $config.ContainsKey('interval_seconds')) { $config['interval_seconds'] = 20 }
    $temporary = $configFile + '.new'
    [IO.File]::WriteAllText($temporary,($config | ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($false)))
    if ([IO.File]::Exists($configFile)) {
        $backup = $configFile + '.previous'
        [IO.File]::Replace($temporary,$configFile,$backup)
        [IO.File]::Delete($backup)
    } else { [IO.File]::Move($temporary,$configFile) }

    if (-not ('VMConsoleRunner' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
public static class VMConsoleRunner {
    [StructLayout(LayoutKind.Sequential)] struct Basic { public long ProcessTime,JobTime; public uint Flags; public UIntPtr Min,Max; public uint Processes; public UIntPtr Affinity; public uint Priority,Scheduling; }
    [StructLayout(LayoutKind.Sequential)] struct Io { public ulong ReadOps,WriteOps,OtherOps,ReadBytes,WriteBytes,OtherBytes; }
    [StructLayout(LayoutKind.Sequential)] struct Limits { public Basic Basic; public Io Io; public UIntPtr ProcessMemory,JobMemory,PeakProcess,PeakJob; }
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr security,string name);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job,int infoClass,ref Limits limits,uint size);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job,IntPtr process);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    static string Quote(string value) {
        var result=new StringBuilder("\"");int n=0;
        foreach(char c in value) { if(c=='\\'){n++;continue;} if(c=='"')result.Append('\\',n*2+1).Append(c);else result.Append('\\',n).Append(c);n=0; }
        return result.Append('\\',n*2).Append('"').ToString();
    }
    public static int Run(string python,string script,string data,int port) {
        IntPtr job=CreateJobObject(IntPtr.Zero,null);if(job==IntPtr.Zero)throw new Win32Exception();
        var limits=new Limits();limits.Basic.Flags=0x2000;
        if(!SetInformationJobObject(job,9,ref limits,(uint)Marshal.SizeOf(limits))) { CloseHandle(job);throw new Win32Exception(); }
        var stop=new ManualResetEvent(false);
        ConsoleCancelEventHandler cancel=(s,e)=>{e.Cancel=true;stop.Set();};Console.CancelKeyPress+=cancel;
        var start=new ProcessStartInfo(python,"-u "+Quote(script)+" --data-dir "+Quote(data)+" --port "+port+" --service-mode") {
            UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=System.IO.Path.GetDirectoryName(script),
            RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true,
            StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8
        };
        using(var process=new Process{StartInfo=start}) {
            bool started=false;
            process.OutputDataReceived+=(s,e)=>{if(e.Data!=null)Console.WriteLine(e.Data);};
            process.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)Console.Error.WriteLine(e.Data);};
            try {
                process.Start();started=true;
                if(!AssignProcessToJobObject(job,process.Handle))throw new Win32Exception();
                process.BeginOutputReadLine();process.BeginErrorReadLine();
                while(!process.WaitForExit(100)) { if(stop.WaitOne(0))break; }
                if(!process.HasExited) { process.StandardInput.WriteLine("stop");process.StandardInput.Flush();if(!process.WaitForExit(10000)){CloseHandle(job);job=IntPtr.Zero;process.WaitForExit(2000);} }
                process.WaitForExit();return stop.WaitOne(0)?0:process.ExitCode;
            } finally {
                Console.CancelKeyPress-=cancel;
                if(started&&!process.HasExited) { try{process.StandardInput.WriteLine("stop");process.StandardInput.Flush();process.WaitForExit(1000);}catch{} }
                if(job!=IntPtr.Zero)CloseHandle(job);stop.Dispose();
            }
        }
    }
}
'@
    }
    $result = [VMConsoleRunner]::Run($resolved.Python,(Join-Path $PSScriptRoot 'replay_service.py'),$DataDirectory,$Port)
    exit $result
} catch {
    Write-Error $_
    exit 1
}
