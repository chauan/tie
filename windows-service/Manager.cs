using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Security.AccessControl;
using System.Security.Principal;
using System.ServiceProcess;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

namespace ReplayRadar {
    internal static class ServiceOps {
        static string Sc { get { return Path.Combine(Environment.SystemDirectory,"sc.exe"); } }
        public static bool Exists { get { using (var key=Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services\"+Common.ServiceName)) return key!=null; } }
        public static string Status() {
            if (!Exists) return "Chưa cài Windows Service";
            using (var controller=new ServiceController(Common.ServiceName)) return controller.Status.ToString();
        }
        static void Owned() {
            string marker=Path.Combine(Common.InstallRoot,"install-info.json");
            if (Common.Text(Common.ReadJson(marker),"application","")!=Common.AppId) throw new InvalidOperationException("The installation folder is not owned by Replay Radar.");
            if (!Exists) return;
            using (var key=Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services\"+Common.ServiceName)) {
                string image=Convert.ToString(key.GetValue("ImagePath"));
                string expected=Common.Quote(Path.Combine(Common.InstallRoot,"ReplayRadar.Service.exe"));
                if (!image.StartsWith(expected+" ",StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("An unrelated service uses the name ReplayRadar. It was left unchanged.");
            }
        }
        public static void Stop() {
            Owned(); if (!Exists) return;
            using (var c=new ServiceController(Common.ServiceName)) {
                if (c.Status!=ServiceControllerStatus.Stopped) { c.Stop(); c.WaitForStatus(ServiceControllerStatus.Stopped,TimeSpan.FromSeconds(25)); }
            }
        }
        public static void Start() {
            Owned();
            using (var c=new ServiceController(Common.ServiceName)) {
                if (c.Status!=ServiceControllerStatus.Running) { c.Start(); c.WaitForStatus(ServiceControllerStatus.Running,TimeSpan.FromSeconds(30)); }
            }
        }
        static void CopyFile(string from,string to) { Directory.CreateDirectory(Path.GetDirectoryName(to)); File.Copy(from,to,true); }
        static void CopyTree(string from,string to) {
            if ((File.GetAttributes(from)&FileAttributes.ReparsePoint)!=0) throw new IOException("Installation source contains a directory junction: "+from);
            Directory.CreateDirectory(to);
            foreach(string file in Directory.GetFiles(from)) CopyFile(file,Path.Combine(to,Path.GetFileName(file)));
            foreach(string dir in Directory.GetDirectories(from)) CopyTree(dir,Path.Combine(to,Path.GetFileName(dir)));
        }
        static string Latest(string folder) {
            return Directory.GetDirectories(folder).Where(p=>Path.GetFileName(p).StartsWith("10.")).OrderByDescending(p=>new Version(Path.GetFileName(p))).First();
        }
        static void CopyApp(string source) {
            if (Common.SamePath(source,Common.InstallRoot)) return;
            foreach(string file in new[]{"ReplayRadar.exe","ReplayRadar.exe.config","ReplayRadar.Service.exe","ReplayRadar.Service.exe.config","replay_service.py","WINDOWS-SERVICE.md","MAP-SOURCES.md"}) CopyFile(Path.Combine(source,file),Path.Combine(Common.InstallRoot,file));
            CopyTree(Path.Combine(source,"web"),Path.Combine(Common.InstallRoot,"web"));
            string legacy=Path.Combine(Common.InstallRoot,"web/assets/player-profile.json"); if(File.Exists(legacy)) File.Delete(legacy);
            CopyTree(Path.Combine(source,"runtime/python"),Path.Combine(Common.InstallRoot,"runtime/python"));
            foreach(string file in new[]{"dotnet.exe","LICENSE.txt","ThirdPartyNotices.txt"}) CopyFile(Path.Combine(source,"runtime/dotnet",file),Path.Combine(Common.InstallRoot,"runtime/dotnet",file));
            foreach(string folder in new[]{"host/fxr","shared/Microsoft.NETCore.App","shared/Microsoft.AspNetCore.App"}) {
                string version=Latest(Path.Combine(source,"runtime/dotnet",folder));
                CopyTree(version,Path.Combine(Common.InstallRoot,"runtime/dotnet",folder,Path.GetFileName(version)));
            }
            foreach(string file in new[]{"IsleDecoder.dll","IsleDecoder.deps.json","IsleDecoder.runtimeconfig.json"}) CopyFile(Path.Combine(source,"decoder/bin",file),Path.Combine(Common.InstallRoot,"decoder/bin",file));
            string license=Path.Combine(source,"licenses/UNREAL-LICENSE.txt");
            if(!File.Exists(license)) license=Path.Combine(source,"vendor/UNREAL-LICENSE.txt");
            CopyFile(license,Path.Combine(Common.InstallRoot,"licenses/UNREAL-LICENSE.txt"));
        }
        static void Grant(string path,SecurityIdentifier sid,FileSystemRights rights) {
            var info=new DirectoryInfo(path); var acl=info.GetAccessControl();
            acl.AddAccessRule(new FileSystemAccessRule(sid,rights,InheritanceFlags.ContainerInherit|InheritanceFlags.ObjectInherit,PropagationFlags.None,AccessControlType.Allow));
            info.SetAccessControl(acl);
        }
        static void RemoveGrant(string path,SecurityIdentifier sid) {
            if(!Directory.Exists(path)) return;
            var info=new DirectoryInfo(path); var acl=info.GetAccessControl();
            acl.PurgeAccessRules(sid); info.SetAccessControl(acl);
        }
        static string ValidateSource(string source) {
            source=Path.GetFullPath(source).TrimEnd('\\');
            if(!Directory.Exists(source)||source.StartsWith(@"\\")||Common.SamePath(source,Path.GetPathRoot(source))) throw new ArgumentException("Choose the existing local replay folder, not a drive root or network share.");
            return source;
        }
        static string ValidateFilename(string source,string filename) {
            if(String.IsNullOrEmpty(filename)) return "";
            if(Path.GetFileName(filename)!=filename||!filename.EndsWith(".replay",StringComparison.OrdinalIgnoreCase)||!File.Exists(Path.Combine(source,filename))) throw new ArgumentException("Chọn file .replay có trong thư mục nguồn.");
            return filename;
        }
        static bool Overlaps(string a,string b) {
            a=Path.GetFullPath(a).TrimEnd('\\')+"\\"; b=Path.GetFullPath(b).TrimEnd('\\')+"\\";
            return a.StartsWith(b,StringComparison.OrdinalIgnoreCase)||b.StartsWith(a,StringComparison.OrdinalIgnoreCase);
        }
        static string ValidateCopies(string source,string copies) {
            if(String.IsNullOrEmpty(copies)) copies=Common.Text(Common.ReadJson(Path.Combine(Common.DataRoot,"config.json")),"copy_dir",Path.Combine(Common.DataRoot,"snapshots"));
            copies=Path.GetFullPath(copies).TrimEnd('\\');
            if(copies.StartsWith(@"\\")||Common.SamePath(copies,Path.GetPathRoot(copies))||Overlaps(source,copies)||Overlaps(Common.InstallRoot,copies)) throw new ArgumentException("Chọn thư mục bản sao riêng, ngoài thư mục replay gốc và thư mục chương trình.");
            return copies;
        }
        public static object Plan(string bundle,string source,int port,string owner,string filename=null,string copies=null) {
            Common.ValidateBundle(bundle); source=ValidateSource(source); Common.Port(new Dictionary<string,object>{{"port",port}}); new SecurityIdentifier(owner);
            if(filename!=null) ValidateFilename(source,filename);
            copies=ValidateCopies(source,copies);
            if(Directory.Exists(Common.InstallRoot)&&Directory.EnumerateFileSystemEntries(Common.InstallRoot).Any()) Owned();
            if(Exists) Owned();
            return new { application=Common.AppId, service_name=Common.ServiceName, display_name="Replay Radar (The Isle)",
                install_directory=Common.InstallRoot, data_directory=Common.DataRoot, replay_directory=source, filename=filename, copy_directory=copies,
                port=port, startup="Automatic (Delayed Start)", account=@"NT SERVICE\ReplayRadar", replay_access="Read only",
                backend="Bundled Python; no CMD or PowerShell at runtime", owner_sid=owner };
        }
        public static void Install(string bundle,string source,int port,string owner,string filename=null,string copies=null) {
            Plan(bundle,source,port,owner,filename,copies); source=ValidateSource(source); copies=ValidateCopies(source,copies);
            bool existed=Exists; if(existed) Stop();
            Directory.CreateDirectory(Common.InstallRoot); Directory.CreateDirectory(Common.DataRoot); Directory.CreateDirectory(copies);
            CopyApp(bundle);
            if(!File.Exists(Path.Combine(Common.InstallRoot,"install-info.json"))) Common.WriteJson(Path.Combine(Common.InstallRoot,"install-info.json"),new{application=Common.AppId,sources=new string[0],owner_sid=owner});
            // Retain the currently chosen profile and compressed history on first install.
            foreach(string file in new[]{"player-profile.json","latest.json"}) {
                string from=Path.Combine(bundle,"data",file), to=Path.Combine(Common.DataRoot,file);
                if(File.Exists(from)&&!File.Exists(to)) CopyFile(from,to);
            }
            string history=Path.Combine(bundle,"data/history"), targetHistory=Path.Combine(Common.DataRoot,"history");
            if(Directory.Exists(history)&&!Directory.Exists(targetHistory)) CopyTree(history,targetHistory);
            var config=Common.ReadJson(Path.Combine(Common.DataRoot,"config.json"));
            if(config.Count==0) {
                config=Common.ReadJson(Path.Combine(bundle,"data/config.json"));
                if(config.Count==0) config=Common.ReadJson(Path.Combine(bundle,"config.json"));
            }
            config["source_dir"]=source; if(filename!=null) config["filename"]=ValidateFilename(source,filename); if(!config.ContainsKey("filename")) config["filename"]=""; config["copy_dir"]=copies; if(!config.ContainsKey("interval_seconds")) config["interval_seconds"]=180;
            Common.WriteJson(Path.Combine(Common.DataRoot,"config.json"),config);
            Common.WriteJson(Path.Combine(Common.DataRoot,"service-host.json"),new{port=port});
            string binary=Common.Join(new[]{Path.Combine(Common.InstallRoot,"ReplayRadar.Service.exe"),"--data-dir",Common.DataRoot});
            if(!existed) Common.Run(Sc,"create",Common.ServiceName,"binPath=",binary,"start=","auto","obj=",@"NT SERVICE\ReplayRadar","DisplayName=","Replay Radar (The Isle)");
            Common.Run(Sc,"sidtype",Common.ServiceName,"unrestricted");
            Common.Run(Sc,"config",Common.ServiceName,"start=","delayed-auto");
            Common.Run(Sc,"description",Common.ServiceName,"Reads local The Isle replay snapshots and serves the Gateway map on localhost.");
            Common.Run(Sc,"failure",Common.ServiceName,"reset=","86400","actions=","restart/5000/restart/15000/restart/60000");
            Common.Run(Sc,"failureflag",Common.ServiceName,"1");
            var sid=(SecurityIdentifier)new NTAccount(@"NT SERVICE\ReplayRadar").Translate(typeof(SecurityIdentifier));
            Grant(Common.InstallRoot,sid,FileSystemRights.ReadAndExecute); Grant(Common.DataRoot,sid,FileSystemRights.Modify);
            Grant(Common.DataRoot,new SecurityIdentifier(owner),FileSystemRights.Modify); Grant(source,sid,FileSystemRights.ReadAndExecute);
            Grant(copies,sid,FileSystemRights.Modify); Grant(copies,new SecurityIdentifier(owner),FileSystemRights.Modify);
            var previous=Common.ReadJson(Path.Combine(Common.InstallRoot,"install-info.json"));
            var sources=new HashSet<string>(StringComparer.OrdinalIgnoreCase); object old;
            if(previous.TryGetValue("sources",out old)&&old is System.Collections.IEnumerable) foreach(object item in (System.Collections.IEnumerable)old) if(item is string) sources.Add((string)item);
            sources.Add(source);
            var workspaces=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if(previous.TryGetValue("copy_folders",out old)&&old is System.Collections.IEnumerable) foreach(object item in (System.Collections.IEnumerable)old) if(item is string) workspaces.Add((string)item);
            workspaces.Add(copies);
            Common.WriteJson(Path.Combine(Common.InstallRoot,"install-info.json"),new{application=Common.AppId,sources=sources.ToArray(),copy_folders=workspaces.ToArray(),owner_sid=owner});
            var health=Common.Health(port);
            if(health!=null) {
                string root=Common.Text(health,"service_root","");
                if(Common.Text(health,"application","")!="isle-replay-radar"||(!Common.SamePath(root,bundle)&&!Common.SamePath(root,Common.InstallRoot))) throw new InvalidOperationException("Port belongs to another program. Existing program was left running.");
                using(var process=Process.GetProcessById(Convert.ToInt32(health["pid"]))) { process.Kill(); process.WaitForExit(5000); }
            }
            Start();
        }
        public static void Uninstall() {
            Owned(); Stop();
            var sid=(SecurityIdentifier)new NTAccount(@"NT SERVICE\ReplayRadar").Translate(typeof(SecurityIdentifier));
            object paths; var marker=Common.ReadJson(Path.Combine(Common.InstallRoot,"install-info.json"));
            if(marker.TryGetValue("sources",out paths)&&paths is System.Collections.IEnumerable) foreach(object p in (System.Collections.IEnumerable)paths) if(p is string) RemoveGrant((string)p,sid);
            if(marker.TryGetValue("copy_folders",out paths)&&paths is System.Collections.IEnumerable) foreach(object p in (System.Collections.IEnumerable)paths) if(p is string) RemoveGrant((string)p,sid);
            RemoveGrant(Common.DataRoot,sid); Common.Run(Sc,"delete",Common.ServiceName);
            // Keep the installed manager and all user data, so it can be installed again.
        }
    }

    internal sealed class ManagerForm : Form {
        readonly TextBox source=new TextBox(), copies=new TextBox(), info=new TextBox();
        readonly ComboBox replay=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList};
        readonly NumericUpDown port=new NumericUpDown{Minimum=1024,Maximum=65535,Value=8765};
        readonly Label status=new Label(); readonly Button install=new Button();
        readonly Timer timer=new Timer{Interval=2000};
        readonly string bundle=AppDomain.CurrentDomain.BaseDirectory;
        public ManagerForm() {
            Text="Replay Radar · Windows Service"; StartPosition=FormStartPosition.CenterScreen; ClientSize=new Size(720,660);
            FormBorderStyle=FormBorderStyle.FixedSingle; MaximizeBox=false; Font=new Font("Segoe UI",10); BackColor=Color.FromArgb(16,25,20); ForeColor=Color.FromArgb(224,237,225);
            var heading=new Label{Text="REPLAY RADAR",Font=new Font("Segoe UI",20,FontStyle.Bold),Bounds=new Rectangle(26,22,620,42)};
            Controls.Add(heading); Controls.Add(new Label{Text="Chạy nền bằng Windows Service · tự khởi động cùng Windows",Bounds=new Rectangle(28,71,625,24)});
            status.SetBounds(28,112,620,28); status.Font=new Font(Font,FontStyle.Bold); Controls.Add(status);
            Controls.Add(new Label{Text="1. Thư mục chứa file .replay gốc",Bounds=new Rectangle(28,155,660,24)});
            source.SetBounds(28,183,548,27); Controls.Add(source);
            var browse=Button("Chọn folder…",586,182,108); browse.Click+=(s,e)=>{using(var dialog=new FolderBrowserDialog{SelectedPath=source.Text,Description="Chọn folder chứa demo.replay hoặc bản ghi muốn theo dõi"}) if(dialog.ShowDialog(this)==DialogResult.OK){source.Text=dialog.SelectedPath;RefreshFiles("demo.replay");}};
            Controls.Add(new Label{Text="2. File trong thư mục đã chọn",Bounds=new Rectangle(28,232,660,24)}); replay.SetBounds(28,260,548,28); Controls.Add(replay);
            Button("Làm mới",586,257,108).Click+=(s,e)=>RefreshFiles(replay.SelectedIndex>0?replay.Text:"");
            Controls.Add(new Label{Text="3. Thư mục bản sao để quét / giải mã",Bounds=new Rectangle(28,310,660,24)}); copies.SetBounds(28,338,548,27); Controls.Add(copies);
            Button("Chọn folder…",586,337,108).Click+=(s,e)=>{using(var dialog=new FolderBrowserDialog{SelectedPath=copies.Text,Description="Chọn thư mục riêng để lưu và quét bản sao replay"}) if(dialog.ShowDialog(this)==DialogResult.OK) copies.Text=dialog.SelectedPath;};
            Controls.Add(new Label{Text="Mỗi 3 phút: sao chép file gốc → thư mục bản sao → giải mã bản sao.",Bounds=new Rectangle(28,382,665,28),ForeColor=Color.FromArgb(155,196,169)});
            Controls.Add(new Label{Text="Cổng localhost",Bounds=new Rectangle(28,426,120,24)}); port.SetBounds(155,425,95,28); Controls.Add(port);
            install.Text="Lưu / cập nhật dịch vụ"; Style(install); install.SetBounds(28,475,220,36); Controls.Add(install); install.Click+=(s,e)=>Action("--install");
            Button("Chạy",259,475,92).Click+=(s,e)=>Action("--start"); Button("Dừng",362,475,92).Click+=(s,e)=>Action("--stop"); Button("Gỡ dịch vụ",465,475,177).Click+=(s,e)=>Action("--uninstall");
            Button("Mở web",28,523,140).Click+=(s,e)=>Process.Start("http://127.0.0.1:"+port.Value);
            Button("Mở bản sao",180,523,145).Click+=(s,e)=>{if(Directory.Exists(copies.Text)) Process.Start("explorer.exe",Common.Quote(copies.Text));};
            Button("Mở log",337,523,115).Click+=(s,e)=>{if(Directory.Exists(Common.DataRoot)) Process.Start("explorer.exe",Common.Quote(Common.DataRoot));};
            info.Multiline=true; info.ReadOnly=true; info.BorderStyle=BorderStyle.None; info.BackColor=BackColor; info.ForeColor=Color.FromArgb(155,181,164); info.SetBounds(28,580,665,63);
            info.Text="Lưu thay đổi thư mục cần quyền quản trị Windows (UAC).\r\nFile gốc chỉ được đọc để sao chép; bộ giải mã chỉ nhận bản sao."; Controls.Add(info);
            var cfg=Common.ReadJson(Path.Combine(Common.DataRoot,"config.json"));
            if(cfg.Count==0) cfg=Common.ReadJson(Path.Combine(bundle,"data/config.json")); if(cfg.Count==0) cfg=Common.ReadJson(Path.Combine(bundle,"config.json"));
            source.Text=Common.Text(cfg,"source_dir",Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"TheIsle/Saved/Demos"));
            copies.Text=Common.Text(cfg,"copy_dir",Path.Combine(Common.DataRoot,"snapshots"));
            source.TextChanged+=(s,e)=>RefreshFiles(""); RefreshFiles(Common.Text(cfg,"filename",""));
            port.Value=Common.Port(Common.ReadJson(Path.Combine(Common.DataRoot,"service-host.json")));
            timer.Tick+=(s,e)=>RefreshStatus(); timer.Start(); RefreshStatus();
        }
        static void Style(Button b) { b.FlatStyle=FlatStyle.Flat; b.FlatAppearance.BorderColor=Color.FromArgb(70,103,80); b.BackColor=Color.FromArgb(33,60,43); b.ForeColor=Color.FromArgb(216,242,221); }
        Button Button(string text,int x,int y,int width) { var b=new Button{Text=text}; Style(b); b.SetBounds(x,y,width,36); Controls.Add(b); return b; }
        void RefreshFiles(string preferred) {
            replay.Items.Clear(); replay.Items.Add("Tự chọn file mới nhất");
            try{if(Directory.Exists(source.Text)) foreach(string file in Directory.GetFiles(source.Text,"*.replay").OrderBy(p=>Path.GetFileName(p))) replay.Items.Add(Path.GetFileName(file));}catch(IOException){}catch(UnauthorizedAccessException){}
            int index=replay.Items.IndexOf(preferred); replay.SelectedIndex=index>0?index:0;
        }
        void RefreshStatus() { try{status.Text="Windows Service: "+ServiceOps.Status();}catch(Exception e){status.Text=e.Message;} }
        async void Action(string action) {
            if(action=="--uninstall"&&MessageBox.Show(this,"Gỡ Windows Service? Dữ liệu và nhật ký được giữ lại.","Replay Radar",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return;
            var args=new[]{action,"--source",source.Text,"--file",replay.SelectedIndex>0?replay.Text:"","--copy-dir",copies.Text,"--port",port.Value.ToString(),"--owner",WindowsIdentity.GetCurrent().User.Value};
            Enabled=false;
            try { int code=await Task.Run(()=>ManagerProgram.Elevate(args)); if(code!=0) MessageBox.Show(this,"Thao tác chưa hoàn tất. Nếu Windows hỏi quyền quản trị, cần chấp nhận để thay đổi dịch vụ.",Text); }
            catch(Exception e){MessageBox.Show(this,e.Message,Text,MessageBoxButtons.OK,MessageBoxIcon.Error);}finally{Enabled=true;RefreshStatus();}
        }
    }
    internal static class ManagerProgram {
        public static int Elevate(string[] args) {
            var principal=new WindowsPrincipal(WindowsIdentity.GetCurrent());
            if(principal.IsInRole(WindowsBuiltInRole.Administrator)) return Execute(args);
            var list=new List<string>(args); list.Add("--elevated");
            var start=new ProcessStartInfo(Application.ExecutablePath,Common.Join(list)){UseShellExecute=true,Verb="runas"};
            using(var process=Process.Start(start)){process.WaitForExit();return process.ExitCode;}
        }
        static int Execute(string[] args) {
            string root=AppDomain.CurrentDomain.BaseDirectory,source=Common.Arg(args,"--source",""); int port=Int32.Parse(Common.Arg(args,"--port","8765"));
            if(Array.IndexOf(args,"--install")>=0) ServiceOps.Install(root,source,port,Common.Arg(args,"--owner",WindowsIdentity.GetCurrent().User.Value),Common.Arg(args,"--file",null),Common.Arg(args,"--copy-dir",null));
            else if(Array.IndexOf(args,"--start")>=0) ServiceOps.Start(); else if(Array.IndexOf(args,"--stop")>=0) ServiceOps.Stop(); else if(Array.IndexOf(args,"--uninstall")>=0) ServiceOps.Uninstall();
            else throw new ArgumentException("Unknown service action."); return 0;
        }
        [STAThread] static int Main(string[] args) {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            try {
                if(Array.IndexOf(args,"--plan")>=0) {
                    object plan=ServiceOps.Plan(AppDomain.CurrentDomain.BaseDirectory,Common.Arg(args,"--source",""),Int32.Parse(Common.Arg(args,"--port","8765")),WindowsIdentity.GetCurrent().User.Value,Common.Arg(args,"--file",null),Common.Arg(args,"--copy-dir",null));
                    Common.WriteJson(Common.Arg(args,"--output","install-plan.json"),plan); return 0;
                }
                if(Array.IndexOf(args,"--screenshot")>=0) { using(var form=new ManagerForm()) { form.ShowInTaskbar=false;form.Opacity=0;form.Show();Application.DoEvents();using(var bitmap=new Bitmap(form.Width,form.Height)){form.DrawToBitmap(bitmap,new Rectangle(0,0,form.Width,form.Height));bitmap.Save(Common.Arg(args,"--screenshot","manager.png"));}form.Close();}return 0; }
                if(args.Length>0) {
                    if(Array.IndexOf(args,"--elevated")>=0) {
                        if(!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator)) throw new UnauthorizedAccessException("Windows administrator approval is required.");
                        return Execute(args);
                    }
                    return Elevate(args);
                }
                Application.Run(new ManagerForm()); return 0;
            } catch(Exception e) { MessageBox.Show(e.Message,"Replay Radar",MessageBoxButtons.OK,MessageBoxIcon.Error); return 1; }
        }
    }
}
