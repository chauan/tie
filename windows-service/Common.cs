using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Web.Script.Serialization;

namespace ReplayRadar {
    internal static class Common {
        public const string ServiceName = "ReplayRadar";
        public const string AppId = "isle-replay-radar-windows-service";
        public static readonly string InstallRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "ReplayRadar");
        public static readonly string DataRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "ReplayRadar");
        public static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 16 * 1024 * 1024 };
        public static string Arg(string[] args, string name, string fallback) {
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : fallback;
        }
        public static string Quote(string value) {
            var result = new StringBuilder("\""); int slashes = 0;
            foreach (char c in value) {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') result.Append('\\', slashes * 2 + 1).Append('"');
                else result.Append('\\', slashes).Append(c);
                slashes = 0;
            }
            return result.Append('\\', slashes * 2).Append('"').ToString();
        }
        public static string Join(IEnumerable<string> args) { return String.Join(" ", args.Select(Quote).ToArray()); }
        public static Dictionary<string, object> ReadJson(string path) {
            return File.Exists(path) ? Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path, Encoding.UTF8)) : new Dictionary<string, object>();
        }
        public static void WriteJson(string path, object data) {
            Directory.CreateDirectory(Path.GetDirectoryName(path)); string temp = path + ".new";
            File.WriteAllText(temp, Json.Serialize(data), new UTF8Encoding(false));
            if (File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
        }
        public static string Text(Dictionary<string, object> data, string key, string fallback) {
            object value; return data.TryGetValue(key, out value) && value is string ? (string)value : fallback;
        }
        public static int Port(Dictionary<string, object> data) {
            object value; int port;
            if (!data.TryGetValue("port", out value)) return 8765;
            if (!Int32.TryParse(Convert.ToString(value), out port) || port < 1024 || port > 65535) throw new InvalidDataException("Port must be between 1024 and 65535.");
            return port;
        }
        public static Dictionary<string, object> Health(int port) {
            try {
                var req = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + port + "/api/health"); req.Timeout = 800; req.Proxy = null;
                using (var response = req.GetResponse()) using (var reader = new StreamReader(response.GetResponseStream())) {
                    return Json.Deserialize<Dictionary<string, object>>(reader.ReadToEnd());
                }
            } catch (WebException) { return null; }
        }
        public static bool SamePath(string a, string b) {
            return String.Equals(Path.GetFullPath(a).TrimEnd('\\'), Path.GetFullPath(b).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase);
        }
        public static void Run(string exe, params string[] args) {
            var start = new ProcessStartInfo(exe, Join(args)) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
            using (var process = Process.Start(start)) {
                var output = process.StandardOutput.ReadToEndAsync(); var error = process.StandardError.ReadToEndAsync();
                if (!process.WaitForExit(30000)) { process.Kill(); throw new TimeoutException(Path.GetFileName(exe) + " timed out."); }
                if (process.ExitCode != 0) throw new InvalidOperationException(Path.GetFileName(exe) + " failed (" + process.ExitCode + "): " + output.Result + error.Result);
            }
        }
        public static void ValidateBundle(string root) {
            foreach (string name in new[] { "ReplayRadar.exe", "ReplayRadar.Service.exe", "replay_service.py", "runtime/python/python.exe", "runtime/dotnet/dotnet.exe", "decoder/bin/IsleDecoder.dll", "web/index.html" })
                if (!File.Exists(Path.Combine(root, name))) throw new FileNotFoundException("Extract the complete Replay Radar package. Missing: " + name);
        }
    }
}
