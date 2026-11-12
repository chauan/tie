using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.ServiceProcess;
using System.Text;
using System.Threading;

namespace ReplayRadar {
    internal sealed class ChildJob : IDisposable {
        IntPtr handle;
        [StructLayout(LayoutKind.Sequential)] struct BasicLimits { public long PerProcessUserTimeLimit, PerJobUserTimeLimit; public uint LimitFlags; public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize; public uint ActiveProcessLimit; public UIntPtr Affinity; public uint PriorityClass, SchedulingClass; }
        [StructLayout(LayoutKind.Sequential)] struct IoCounters { public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount, ReadTransferCount, WriteTransferCount, OtherTransferCount; }
        [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits { public BasicLimits Basic; public IoCounters Io; public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed; }
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr security, string name);
        [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref ExtendedLimits info, uint size);
        [DllImport("kernel32.dll", SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
        public ChildJob() {
            handle = CreateJobObject(IntPtr.Zero, null); if (handle == IntPtr.Zero) throw new Win32Exception();
            var info = new ExtendedLimits(); info.Basic.LimitFlags = 0x2000;
            if (!SetInformationJobObject(handle, 9, ref info, (uint)Marshal.SizeOf(info))) { Dispose(); throw new Win32Exception(); }
        }
        public void Add(Process process) { if (!AssignProcessToJobObject(handle, process.Handle)) throw new Win32Exception(); }
        public void Dispose() { if (handle != IntPtr.Zero) { CloseHandle(handle); handle = IntPtr.Zero; } }
    }
    internal sealed class BackendHost : IDisposable {
        Process child; ChildJob job;
        readonly string appRoot, dataRoot; readonly int port; readonly object logLock = new object();
        public volatile bool Stopping;
        public int ProcessId { get { return child.Id; } }
        public bool Running { get { return child != null && !child.HasExited; } }
        public event Action Failed;
        public BackendHost(string appRoot, string dataRoot, int port) { this.appRoot = appRoot; this.dataRoot = dataRoot; this.port = port; }
        void Log(string text) {
            if (String.IsNullOrEmpty(text)) return;
            lock (logLock) {
                string file = Path.Combine(dataRoot, "windows-service.log");
                if (File.Exists(file) && new FileInfo(file).Length > 5 * 1024 * 1024) { string old = file + ".1"; if (File.Exists(old)) File.Delete(old); File.Move(file, old); }
                File.AppendAllText(file, DateTimeOffset.Now.ToString("o") + " " + text + Environment.NewLine, new UTF8Encoding(false));
            }
        }
        public void Start() {
            Common.ValidateBundle(appRoot); Directory.CreateDirectory(dataRoot);
            if (Common.Health(port) != null) throw new InvalidOperationException("Port " + port + " is already in use; existing application was left running.");
            var info = new ProcessStartInfo(Path.Combine(appRoot, "runtime/python/python.exe"), Common.Join(new[] { "-u", Path.Combine(appRoot, "replay_service.py"), "--data-dir", dataRoot, "--port", port.ToString(), "--service-mode" })) {
                UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = appRoot, RedirectStandardInput = true,
                RedirectStandardOutput = true, RedirectStandardError = true, StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            info.EnvironmentVariables["PYTHONUTF8"] = "1";
            child = new Process { StartInfo = info, EnableRaisingEvents = true };
            child.OutputDataReceived += (s,e) => { try { Log(e.Data); } catch { } };
            child.ErrorDataReceived += (s,e) => { try { Log(e.Data); } catch { } };
            child.Exited += (s,e) => { if (!Stopping) { try { Log("Backend exited unexpectedly."); } catch { } if (Failed != null) Failed(); } };
            job = new ChildJob();
            try {
                child.Start(); job.Add(child); child.BeginOutputReadLine(); child.BeginErrorReadLine();
                for (int i=0; i<60; i++) {
                    if (child.HasExited) throw new InvalidOperationException("Backend exited. Check " + dataRoot + "\\windows-service.log");
                    var health = Common.Health(port);
                    if (health != null && Common.Text(health,"application","") == "isle-replay-radar" && Common.SamePath(Common.Text(health,"service_root",""),appRoot) && Convert.ToInt32(health["pid"]) == child.Id) { Log("Windows service backend ready, PID " + child.Id); return; }
                    Thread.Sleep(100);
                }
                throw new System.TimeoutException("Backend did not become ready.");
            } catch { Dispose(); throw; }
        }
        public void Dispose() {
            Stopping = true;
            if (child != null) {
                try { if (!child.HasExited) { child.StandardInput.WriteLine("stop"); child.StandardInput.Flush(); child.WaitForExit(10000); } } catch (InvalidOperationException) { } catch (IOException) { }
            }
            if (job != null) { job.Dispose(); job = null; }
            if (child != null) { try { child.WaitForExit(2000); } catch (InvalidOperationException) { } child.Dispose(); child = null; }
        }
    }
    internal sealed class RadarService : ServiceBase {
        BackendHost backend; readonly string dataRoot;
        public RadarService(string dataRoot) { this.dataRoot = dataRoot; ServiceName = Common.ServiceName; CanStop = true; CanShutdown = true; AutoLog = true; }
        protected override void OnStart(string[] args) {
            var config = Common.ReadJson(Path.Combine(dataRoot,"service-host.json"));
            backend = new BackendHost(AppDomain.CurrentDomain.BaseDirectory, dataRoot, Common.Port(config));
            backend.Failed += () => { var instance=backend; if (instance!=null&&!instance.Stopping) Environment.Exit(1); }; backend.Start();
        }
        protected override void OnStop() { if (backend != null) { RequestAdditionalTime(15000); backend.Dispose(); backend = null; } }
        protected override void OnShutdown() { if (backend != null) { backend.Dispose(); backend = null; } }
        static int Main(string[] args) {
            string data = Common.Arg(args,"--data-dir",Common.DataRoot);
            if (Array.IndexOf(args,"--probe") >= 0) {
                try {
                    string root = Common.Arg(args,"--app-root",AppDomain.CurrentDomain.BaseDirectory);
                    int port = Int32.Parse(Common.Arg(args,"--port","8767"));
                    using (var host = new BackendHost(root,data,port)) {
                        host.Start(); Common.WriteJson(Path.Combine(data,"probe-ready.json"),new { pid=host.ProcessId, ready=true });
                        string stop = Path.Combine(data,"probe-stop");
                        for (int i=0; i<1200 && !File.Exists(stop) && host.Running; i++) Thread.Sleep(100);
                    }
                    Common.WriteJson(Path.Combine(data,"probe-stopped.json"),new { stopped=true }); return 0;
                } catch (Exception e) { Directory.CreateDirectory(data); File.WriteAllText(Path.Combine(data,"probe-error.txt"),e.ToString()); return 1; }
            }
            ServiceBase.Run(new RadarService(data)); return 0;
        }
    }
}
