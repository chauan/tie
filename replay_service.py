"""Local replay snapshots and Gateway map. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import gzip
import json
import logging
from logging.handlers import RotatingFileHandler
import mimetypes
import os
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote, parse_qs

ROOT = Path(__file__).resolve().parent
# The embedded Windows Python uses an isolated ._pth and omits the script directory.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from telegram_alerts import TelegramAlerts
LOG = logging.getLogger("isle")
MAGIC = 0x1CA2E27F
UI_ASSETS = ("index.html", "app.js", "projection.js", "replay-model.js", "creature-panel.js", "style.css", "features.css", "console.css", "survival.css", "assets/gateway-calibration.json", "assets/survival-icons.svg", "assets/survival-metal.svg", "assets/survival-jungle.png", "assets/survival-dinosaurs.png", "assets/barlow-condensed-semibold.ttf")
_ui_cache = (None, None)
_ui_lock = threading.Lock()
_profile_lock = threading.RLock()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def ui_revision():
    global _ui_cache
    paths = [ROOT / "web" / name for name in UI_ASSETS]
    stamps = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) if p.is_file() else (str(p),) for p in paths)
    with _ui_lock:
        if _ui_cache[0] != stamps:
            digest = hashlib.sha256()
            for name, path in zip(UI_ASSETS, paths):
                digest.update(name.encode("utf-8"))
                if path.is_file():
                    digest.update(path.read_bytes())
            _ui_cache = (stamps, digest.hexdigest()[:16])
        return _ui_cache[1]


def validate_player_profile(value):
    steam_id, name = value.get("steam_id", ""), value.get("name", "")
    if not isinstance(steam_id, str) or not isinstance(name, str):
        raise ValueError("SteamID và tên phải là chuỗi ký tự; giữ SteamID đủ 17 chữ số.")
    steam_id, name = steam_id.strip(), name.strip()
    if steam_id and not re.fullmatch(r"[0-9]{17}", steam_id):
        raise ValueError("SteamID cần đúng 17 chữ số.")
    if len(name) > 60:
        raise ValueError("Tên gợi nhớ tối đa 60 ký tự.")
    return {"steam_id": steam_id, "name": name if steam_id else ""}


def save_player_profile(data_dir, value):
    profile = validate_player_profile(value)
    with _profile_lock:
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        atomic_json(Path(data_dir) / "player-profile.json", profile)
    return profile


def load_player_profile(data_dir):
    path = Path(data_dir) / "player-profile.json"
    with _profile_lock:
        if path.is_file():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                return {**validate_player_profile(saved), "migrated_legacy": saved.get("migrated_legacy") is True}
            except (OSError, ValueError, TypeError, AttributeError):
                return {"steam_id": "", "name": ""}
        legacy = ROOT / "web/assets/player-profile.json"
        if legacy.is_file():
            try:
                profile = {**validate_player_profile(json.loads(legacy.read_text(encoding="utf-8"))), "migrated_legacy": True}
                Path(data_dir).mkdir(parents=True, exist_ok=True)
                atomic_json(path, profile)
                return profile
            except (OSError, ValueError, TypeError, AttributeError):
                LOG.warning("Không chuyển được thiết lập tài khoản cũ; hãy nhập SteamID trên web.")
        return {"steam_id": "", "name": ""}


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def atomic_gzip_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=3) as f:
            json.dump(value, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def fstring(f):
    raw = f.read(4)
    if len(raw) != 4:
        raise ValueError("Replay header chưa đủ dữ liệu.")
    length, = struct.unpack("<i", raw)
    if abs(length) > 16384:
        raise ValueError("Độ dài chuỗi trong replay không hợp lệ.")
    if not length:
        return ""
    data = f.read(abs(length) * (2 if length < 0 else 1))
    if len(data) != abs(length) * (2 if length < 0 else 1):
        raise ValueError("Chuỗi replay bị cắt.")
    return data[:-2 if length < 0 else -1].decode("utf-16le" if length < 0 else "utf-8", errors="replace")


def read_layout(path):
    """Walk chunk headers with seeks; do not load a multi-GB replay into RAM."""
    with path.open("rb") as f:
        limit = os.fstat(f.fileno()).st_size
        if len(prefix := f.read(8)) != 8:
            raise ValueError("Replay chưa có header đầy đủ.")
        magic, version = struct.unpack("<II", prefix)
        if magic != MAGIC or version != 7:
            raise ValueError("Chỉ hỗ trợ Unreal LocalFile replay version 7 đã kiểm tra với The Isle.")
        custom_count, = struct.unpack("<I", f.read(4))
        if custom_count > 32:
            raise ValueError("Custom version count không hợp lệ.")
        f.seek(custom_count * 20, 1)
        duration, network, change = struct.unpack("<III", f.read(12))
        friendly = fstring(f).strip()
        live, ticks, compressed, encrypted, key_size = struct.unpack("<IqIII", f.read(24))
        if key_size > 4096:
            raise ValueError("Encryption key size không hợp lệ.")
        f.seek(key_size, 1)
        header_end = f.tell()
        last_complete = header_end
        chunks = {"header": 0, "data": 0, "checkpoint": 0, "event": 0}
        map_name = "Unknown"
        final_ms = 0
        while f.tell() + 8 <= limit:
            chunk_at = f.tell()
            kind, size = struct.unpack("<II", f.read(8))
            end = f.tell() + size
            if end > limit or size == 0:
                break
            if kind > 3:
                raise ValueError(f"Chunk type không hỗ trợ: {kind} tại {chunk_at}.")
            chunks[("header", "data", "checkpoint", "event")[kind]] += 1
            if kind == 0:
                import re
                data = f.read(min(size, 16384))
                match = re.search(rb"/Game/TheIsle/Maps/Game/([^/\x00]+)/", data)
                if match:
                    map_name = match.group(1).decode("ascii", errors="replace")
            elif kind == 1 and size >= 16:
                begin, stop, stored, memory = struct.unpack("<4I", f.read(16))
                if stored > size - 16 or stop < begin:
                    raise ValueError("Replay data chunk không hợp lệ.")
                final_ms = max(final_ms, stop)
            last_complete = end
            f.seek(end)
        f.seek(0)
        header_bytes = f.read(header_end)
    recorded = dt.datetime(1, 1, 1) + dt.timedelta(microseconds=ticks // 10)
    return {"duration_ms": final_ms or duration, "header_duration_ms": duration,
            "recorded_at": recorded.isoformat(), "recorded_timezone": "unspecified",
            "map": map_name, "live_flag": bool(live), "compressed": bool(compressed),
            "encrypted": bool(encrypted), "network_version": network, "chunks": chunks,
            "source_size": limit, "complete_bytes": last_complete,
            "has_partial_tail": last_complete != limit, "header_bytes": header_bytes}


def copy_snapshot(source, destination):
    """Copy raw bytes first; inspect and decode only the private copy."""
    for attempt in range(3):
        temporary = destination.with_suffix(".part")
        try:
            with source.open("rb") as src, temporary.open("wb") as dst:
                captured = os.fstat(src.fileno())
                remaining = captured.st_size
                while remaining:
                    data = src.read(min(4 * 1024 * 1024, remaining))
                    if not data:
                        raise OSError("Replay nguồn đã bị rút ngắn trong lúc sao chép.")
                    dst.write(data)
                    remaining -= len(data)
                dst.flush()
                os.fsync(dst.fileno())
            layout = read_layout(temporary)
            if not layout["chunks"]["data"]:
                raise ValueError("Replay chưa có khối gameplay hoàn chỉnh. Đợi lần đồng bộ kế tiếp.")
            with source.open("rb") as src:
                current = os.fstat(src.fileno())
                if (current.st_dev, current.st_ino) != (captured.st_dev, captured.st_ino) or current.st_size < captured.st_size:
                    raise OSError("Game vừa thay hoặc rút ngắn replay; đang thử lại bản sao.")
                src.seek(0)
                if src.read(len(layout["header_bytes"])) != layout["header_bytes"]:
                    raise OSError("Game vừa cập nhật header; đang thử lại bản sao.")
            with temporary.open("r+b") as dst:
                dst.truncate(layout["complete_bytes"])
            os.replace(temporary, destination)
            layout.pop("header_bytes")
            return layout
        except (OSError, ValueError, struct.error) as error:
            temporary.unlink(missing_ok=True)
            if attempt == 2 or not isinstance(error, OSError):
                raise
    raise OSError("Không sao chép được replay.")


def prepare_copy_directory(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Thư mục bản sao phải tách riêng, không nằm trong hoặc bao quanh thư mục replay gốc.")
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / ".replay-radar-workspace.json"
    if marker.exists():
        saved = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(saved, dict) or saved.get("application") != "isle-replay-radar-workspace" or not isinstance(saved.get("files", []), list):
            raise ValueError("Thư mục bản sao có thông tin sở hữu không phù hợp.")
    else:
        atomic_json(marker, {"application": "isle-replay-radar-workspace", "files": []})
    return destination


class Collector:
    def __init__(self, source, interval=20, filename="", data_dir=None, copy_dir=None):
        self.source = Path(source).expanduser().resolve()
        self.interval = interval
        self.filename = filename
        self.data_dir = Path(data_dir or ROOT / "data")
        self.snapshots = prepare_copy_directory(self.source, copy_dir or self.data_dir / "snapshots")
        self.history_dir = self.data_dir / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.history = []
        index = self.history_dir / "index.json"
        if index.exists():
            try:
                self.history = [item for item in json.loads(index.read_text(encoding="utf-8"))
                                if re.fullmatch(r"snapshot-[0-9]+", str(item.get("id", "")))
                                and (self.history_dir / (item["id"] + ".json.gz")).is_file()]
            except (ValueError, OSError, TypeError):
                LOG.exception("Không đọc được chỉ mục lịch sử")
        self.lock = threading.RLock()
        self.sync_lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.fingerprint = None
        self.last = None
        self.status = {"phase": "waiting", "message": "Đang chuẩn bị đồng bộ.", "next_sync_at": None,
                       "last_checked_at": None, "last_success_at": None, "error": None}
        self.thread = None
        self.telegram = TelegramAlerts(self.data_dir)
        saved = self.data_dir / "latest.json"
        if saved.exists():
            try:
                self.last = json.loads(saved.read_text(encoding="utf-8"))
                self.status["last_success_at"] = self.last.get("copied_at")
                if (self.history_dir / (self.last.get("id", "") + ".json.gz")).is_file() and self.last.get("source_fingerprint"):
                    self.fingerprint = tuple(self.last["source_fingerprint"])
            except (ValueError, OSError):
                LOG.exception("Không đọc được kết quả cũ")
        if self.snapshots == (self.data_dir / "snapshots").resolve():
            marker = self.snapshots / ".replay-radar-workspace.json"
            owned = json.loads(marker.read_text(encoding="utf-8"))
            if not owned.get("files"):
                known = {item["id"] for item in self.history}
                if self.last and self.last.get("id"):
                    known.add(self.last["id"])
                names = sorted((snapshot_id + ".replay" for snapshot_id in known
                                if re.fullmatch(r"snapshot-[0-9]+", snapshot_id) and (self.snapshots / (snapshot_id + ".replay")).is_file()), reverse=True)
                atomic_json(marker, {"application": "isle-replay-radar-workspace", "files": names})

    def file_list(self, source=None):
        directory = Path(source) if source is not None else self.source
        if not directory.is_dir():
            return []
        result = []
        for p in directory.glob("*.replay"):
            if p.is_file():
                try:
                    s = p.stat()
                    result.append({"name": p.name, "bytes": s.st_size, "modified_ns": s.st_mtime_ns,
                                   "modified_at": dt.datetime.fromtimestamp(s.st_mtime, dt.timezone.utc).isoformat()})
                except OSError:
                    continue
        return sorted(result, key=lambda p: p["modified_ns"], reverse=True)

    def state(self):
        with self.lock:
            replay = {k: v for k, v in self.last.items() if k not in ("entities", "tracks", "source_fingerprint")} if self.last else None
            return {"status": dict(self.status), "source_dir": str(self.source), "interval_seconds": self.interval,
                    "selected_file": self.filename, "files": self.file_list(), "replay": replay, "history": list(self.history),
                    "player_profile": load_player_profile(self.data_dir), "copy_dir": str(self.snapshots),
                    "telegram": self.telegram.public()}

    def save_history(self, result):
        path = self.history_dir / (result["id"] + ".json.gz")
        atomic_gzip_json(path, result)
        entry = {key: result.get(key) for key in ("id", "filename", "copied_at", "recorded_at", "duration_ms", "source_size", "map", "history_sample_seconds")}
        entry.update(entity_count=len(result["entities"]), archive_bytes=path.stat().st_size)
        with self.lock:
            candidates = [entry] + [item for item in self.history if item["id"] != entry["id"]]
            kept, removed, total = [], [], 0
            for item in candidates:
                size = int(item.get("archive_bytes", 0))
                if kept and (len(kept) >= 50 or total + size > 512 * 1024 * 1024):
                    removed.append(item)
                else:
                    kept.append(item)
                    total += size
            atomic_json(self.history_dir / "index.json", kept)
            self.history = kept
        for item in removed:
            try:
                (self.history_dir / (item["id"] + ".json.gz")).unlink(missing_ok=True)
            except OSError:
                LOG.warning("Không xóa được bản lịch sử cũ %s", item["id"])

    def history_payload(self, snapshot_id):
        if not re.fullmatch(r"snapshot-[0-9]+", snapshot_id):
            return None, None
        path = self.history_dir / (snapshot_id + ".json.gz")
        if path.is_file():
            return path.read_bytes(), "gzip"
        with self.lock:
            if self.last and self.last.get("id") == snapshot_id:
                public = {k: v for k, v in self.last.items() if k != "source_fingerprint"}
                return json.dumps(public, ensure_ascii=False, allow_nan=False).encode("utf-8"), None
        return None, None

    def sync(self):
        if not self.sync_lock.acquire(blocking=False):
            return False
        target = None
        try:
            with self.lock:
                self.status.update(phase="copying", message="Đang kiểm tra replay nguồn…", last_checked_at=now(), error=None)
                files = self.file_list()
                if not files:
                    raise ValueError("Chưa thấy file .replay. Bật ghi replay trong game hoặc kiểm tra thư mục nguồn.")
                chosen = next((f for f in files if f["name"] == self.filename), None) if self.filename else files[0]
                if not chosen:
                    raise ValueError(f"Không tìm thấy replay đã chọn: {self.filename}")
                source = self.source / chosen["name"]
                with source.open("rb") as f:
                    identity = hashlib.sha256(f.read(1024)).hexdigest()
                decoder = ROOT / "decoder" / "bin" / "IsleDecoder.dll"
                decoder_revision = hashlib.sha256(decoder.read_bytes()).hexdigest() if decoder.is_file() else "missing"
                fingerprint = (str(source), chosen["modified_ns"], chosen["bytes"], identity, str(self.snapshots), decoder_revision)
                if fingerprint == self.fingerprint and self.last and (self.snapshots / (self.last["id"] + ".replay")).is_file():
                    self.status.update(phase="idle", message="Chưa có thay đổi trong replay nguồn.")
                    return True
                snapshot_id = f"snapshot-{time.time_ns()}"
                self.snapshots = prepare_copy_directory(self.source, self.snapshots)
                target = self.snapshots / f"{snapshot_id}.replay"
            meta = copy_snapshot(source, target)
            if meta["map"] != "Gateway":
                raise ValueError(f"Bản đồ {meta['map']} chưa được hỗ trợ. Service này dùng bản đồ Gateway.")
            with self.lock:
                self.status.update(phase="decoding", message=f"Đang giải mã bản sao của {source.name} trong thư mục riêng…")
            dotnet = ROOT / "runtime" / "dotnet" / "dotnet.exe"
            executable = str(dotnet) if dotnet.exists() else shutil.which("dotnet")
            if not executable:
                raise ValueError("Chưa có .NET 10. Chạy setup.ps1 để cài bộ đọc replay.")
            creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            LOG.info("Decode workspace copy: %s (source filename: %s)", target, source.name)
            decoded = subprocess.run([executable, str(ROOT / "decoder" / "bin" / "IsleDecoder.dll"), str(target)],
                                     capture_output=True, text=True, encoding="utf-8", timeout=150,
                                     creationflags=creation)
            if decoded.returncode:
                raise ValueError("Bộ đọc replay gặp lỗi: " + decoded.stderr[-1600:])
            result = json.loads(decoded.stdout)
            result.update(meta, id=snapshot_id, filename=source.name, copied_at=now(), source_modified_at=chosen["modified_at"])
            if result["diagnostics"]["frames"] == 0:
                raise ValueError("Bộ đọc chưa giải mã được frame; giữ bản cập nhật thành công trước đó.")
            result["timeline_available"] = bool(result.get("tracks"))
            result["entity_count"] = len(result["entities"])
            self.save_history(result)
            latest = {k: v for k, v in result.items() if k != "tracks"}
            latest["source_fingerprint"] = list(fingerprint)
            atomic_json(self.data_dir / "latest.json", latest)
            with self.lock:
                self.last = latest
                self.fingerprint = fingerprint
                self.status.update(phase="idle", message="Đã cập nhật bản đồ từ replay.", last_success_at=result["copied_at"])
            # Retain only copies recorded in our own workspace manifest.
            marker = self.snapshots / ".replay-radar-workspace.json"
            owned = json.loads(marker.read_text(encoding="utf-8"))
            names = [target.name] + [name for name in owned.get("files", [])
                                     if isinstance(name, str) and re.fullmatch(r"snapshot-[0-9]+\.replay", name) and name != target.name]
            kept = names[:3]
            for name in names[3:]:
                old = self.snapshots / name
                try:
                    old.unlink(missing_ok=True)
                except OSError:
                    kept.append(name)
                    LOG.warning("Snapshot cũ đang bị khóa: %s", old.name)
            atomic_json(marker, {"application": "isle-replay-radar-workspace", "files": kept})
            LOG.info("Updated %s: %s entities, %s movement updates", source.name, len(result["entities"]), result["diagnostics"]["movements"])
            self.telegram.submit(result, load_player_profile(self.data_dir))
            return True
        except Exception as error:
            if target:
                target.unlink(missing_ok=True)
            LOG.exception("Đồng bộ chưa thành công")
            with self.lock:
                self.status.update(phase="error", message="Chưa cập nhật được replay; đang giữ kết quả trước.", error=str(error))
            return False
        finally:
            self.sync_lock.release()

    def run(self):
        while not self.stop.is_set():
            self.wake.clear()
            started = time.monotonic()
            self.sync()
            delay = max(0, self.interval - (time.monotonic() - started))
            with self.lock:
                self.status["next_sync_at"] = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=delay)).isoformat()
            self.wake.wait(delay)

    def start(self):
        self.telegram.start()
        self.thread = threading.Thread(target=self.run, name="replay-collector", daemon=True)
        self.thread.start()

    def request_sync(self):
        self.wake.set()


class Handler(BaseHTTPRequestHandler):
    server_version = "IsleReplay/1.0"

    def log_message(self, fmt, *args):
        if args and str(args[1] if len(args) > 1 else "") != "200":
            LOG.info(fmt, *args)

    def allowed_host(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def send_bytes(self, data, content_type, status=200, encoding=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.send_header("Cache-Control", "no-store" if content_type.startswith(("application/json", "text/html")) else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def json(self, value, status=200):
        self.send_bytes(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def do_GET(self):
        if not self.allowed_host():
            return self.json({"error": "Localhost only"}, 403)
        path = unquote(urlsplit(self.path).path)
        if path == "/api/state":
            state = self.server.collector.state()
            state["ui_revision"] = ui_revision()
            return self.json(state)
        if path == "/api/health":
            return self.json({"ok": True, "application": "isle-replay-radar", "service_root": str(ROOT), "pid": os.getpid()})
        if path == "/api/profile":
            return self.json(load_player_profile(self.server.collector.data_dir))
        if path == "/api/source-files":
            try:
                requested = parse_qs(urlsplit(self.path).query).get("source_dir", [""])[0]
                if not requested.strip():
                    raise ValueError("Nhập đường dẫn thư mục chứa replay.")
                directory = Path(requested).expanduser().resolve()
                if not directory.is_dir():
                    raise ValueError("Thư mục nguồn không tồn tại hoặc service chưa có quyền đọc.")
                return self.json({"files": self.server.collector.file_list(directory)})
            except (ValueError, OSError) as error:
                return self.json({"error": str(error)}, 400)
        if path == "/api/history":
            return self.json({"items": self.server.collector.state()["history"]})
        if path.startswith("/api/replays/"):
            try:
                data, encoding = self.server.collector.history_payload(path.removeprefix("/api/replays/"))
            except FileNotFoundError:
                data, encoding = None, None
            if data is None:
                return self.json({"error": "Bản sao này không còn trong lịch sử."}, 404)
            return self.send_bytes(data, "application/json; charset=utf-8", encoding=encoding)
        relative = "index.html" if path == "/" else path.lstrip("/")
        file = (ROOT / "web" / relative).resolve()
        if not file.is_relative_to((ROOT / "web").resolve()) or not file.is_file():
            return self.json({"error": "Not found"}, 404)
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or file.suffix == ".js":
            content_type += "; charset=utf-8"
        data = file.read_bytes()
        if file == ROOT / "web" / "index.html":
            revision = ui_revision()
            data = data.replace(b"<head>", f'<head>\n  <meta name="isle-ui-revision" content="{revision}">'.encode("utf-8"), 1)
            for asset in ("style.css", "features.css", "console.css", "survival.css", "projection.js", "replay-model.js", "creature-panel.js", "app.js"):
                data = data.replace(f'"/{asset}"'.encode("ascii"), f'"/{asset}?v={revision}"'.encode("ascii"))
        return self.send_bytes(data, content_type)

    def do_POST(self):
        origin = self.headers.get("Origin")
        origins = (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")
        if not self.allowed_host() or origin and origin not in origins or self.headers.get("X-Isle-Client") != "1":
            return self.json({"error": "Request rejected"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 8192 or length < 0:
                return self.json({"error": "Request too large"}, 413)
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Yêu cầu cần là một JSON object.")
            if self.path == "/api/profile":
                return self.json(save_player_profile(self.server.collector.data_dir, body))
            if self.path == "/api/sync":
                self.server.collector.request_sync()
                return self.json({"queued": True}, 202)
            if self.path == "/api/telegram":
                if body.get("enabled") and not load_player_profile(self.server.collector.data_dir).get("steam_id"):
                    raise ValueError("Chọn SteamID của bạn trong Radar của bạn trước khi bật Telegram.")
                return self.json(self.server.collector.telegram.configure(body))
            if self.path == "/api/telegram/test":
                return self.json(self.server.collector.telegram.test())
            if self.path == "/api/config":
                source = Path(body["source_dir"]).expanduser().resolve()
                filename = body.get("filename", "")
                if not source.is_dir() or filename and (Path(filename).name != filename or not filename.lower().endswith(".replay")):
                    raise ValueError("Thư mục hoặc tên replay không hợp lệ.")
                c = self.server.collector
                interval = body.get("interval_seconds", c.interval)
                if type(interval) is not int or not 5 <= interval <= 3600:
                    raise ValueError("Chu kỳ đồng bộ phải là số nguyên từ 5 đến 3.600 giây.")
                if not c.sync_lock.acquire(blocking=False):
                    return self.json({"error": "Đang đồng bộ, hãy đợi vài giây rồi thử lại."}, 409)
                try:
                    copies = prepare_copy_directory(source, body.get("copy_dir") or c.snapshots)
                    with c.lock:
                        atomic_json(c.data_dir / "config.json", {"source_dir": str(source), "filename": filename, "copy_dir": str(copies), "interval_seconds": interval})
                        c.interval = interval
                        c.source, c.filename, c.snapshots, c.fingerprint = source, filename, copies, None
                finally:
                    c.sync_lock.release()
                c.request_sync()
                return self.json({"queued": True}, 202)
            return self.json({"error": "Not found"}, 404)
        except (ValueError, KeyError, TypeError, OSError) as error:
            return self.json({"error": str(error)}, 400)


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False


def main():
    location = argparse.ArgumentParser(add_help=False)
    location.add_argument("--data-dir", type=Path, default=ROOT / "data")
    location_args, _ = location.parse_known_args()
    data_dir = location_args.data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    config = {}
    config_path = data_dir / "config.json"
    legacy_config = ROOT / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    elif data_dir == (ROOT / "data").resolve() and legacy_config.exists():
        config = json.loads(legacy_config.read_text(encoding="utf-8"))
    default_source = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "TheIsle/Saved/Demos"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=data_dir)
    parser.add_argument("--service-mode", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--source", default=config.get("source_dir", str(default_source)))
    parser.add_argument("--file", default=config.get("filename", ""))
    parser.add_argument("--copy-dir", type=Path, default=config.get("copy_dir", data_dir / "snapshots"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval", type=int, default=config.get("interval_seconds", 20))
    args = parser.parse_args()
    if args.interval < 5:
        parser.error("interval phải từ 5 giây trở lên")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), RotatingFileHandler(data_dir / "service.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")])
    collector = Collector(args.source, args.interval, args.file, data_dir=data_dir, copy_dir=args.copy_dir)
    server = LocalServer(("127.0.0.1", args.port), Handler)
    server.collector = collector
    collector.start()
    if args.service_mode:
        def control():
            import sys
            for line in sys.stdin:
                if line.strip() == "stop":
                    server.shutdown()
                    return
            # Closing the parent host's input pipe also requests shutdown.
            server.shutdown()
        threading.Thread(target=control, name="service-control", daemon=True).start()
    LOG.info("Gateway map: http://127.0.0.1:%s | source=%s | interval=%ss", args.port, collector.source, args.interval)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        collector.stop.set()
        collector.wake.set()
        server.server_close()
        if collector.thread:
            collector.thread.join(timeout=160)
        collector.telegram.close()


if __name__ == "__main__":
    main()
