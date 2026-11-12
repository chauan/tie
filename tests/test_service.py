import datetime as dt
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import sys
import subprocess
import threading
import gzip

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay_service import MAGIC, Collector, read_layout, copy_snapshot


def replay_bytes(tail=b""):
    epoch = dt.datetime(1, 1, 1)
    ticks = int((dt.datetime(2026, 11, 10, 23, 46, 48) - epoch).total_seconds()) * 10_000_000
    head = struct.pack("<III", MAGIC, 7, 1) + bytes(16) + struct.pack("<IIII", 7, 1000, 42, 0)
    head += struct.pack("<i", 0) + struct.pack("<IqIII", 1, ticks, 0, 0, 0)
    def chunk(kind, value):
        return struct.pack("<II", kind, len(value)) + value
    return head + chunk(0, b"/Game/TheIsle/Maps/Game/Gateway/Gateway\0") + chunk(1, struct.pack("<4I", 0, 1000, 3, 3) + b"abc") + tail


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.dotnet_lookup = patch('replay_service.shutil.which', return_value='dotnet-test')
        self.dotnet_lookup.start()
        self.addCleanup(self.dotnet_lookup.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.file = self.source / "demo3.replay"
        self.file.write_bytes(replay_bytes())

    def tearDown(self):
        self.tmp.cleanup()

    def test_metadata_and_actual_chunk_duration(self):
        result = read_layout(self.file)
        self.assertEqual(result["duration_ms"], 1000)
        self.assertEqual(result["map"], "Gateway")
        self.assertEqual(result["chunks"]["data"], 1)
        self.assertEqual(result["recorded_at"], "2026-11-10T23:46:48")
        self.assertFalse(result["has_partial_tail"])

    def test_copy_ignores_incomplete_tail_and_preserves_original(self):
        original = replay_bytes(struct.pack("<II", 1, 500) + b"unfinished")
        self.file.write_bytes(original)
        target = self.base / "snapshot.replay"
        result = copy_snapshot(self.file, target)
        self.assertEqual(self.file.read_bytes(), original)
        self.assertEqual(target.read_bytes(), replay_bytes())
        self.assertTrue(result["has_partial_tail"])
        self.assertFalse(target.with_suffix(".part").exists())

    def test_bad_magic_rejected(self):
        self.file.write_bytes(b"bad data" + bytes(300))
        with self.assertRaises(ValueError):
            read_layout(self.file)

    def test_truncated_header_rejected(self):
        self.file.write_bytes(b"123")
        with self.assertRaises(ValueError):
            read_layout(self.file)

    def test_unknown_chunk_rejected(self):
        self.file.write_bytes(replay_bytes(struct.pack("<II", 99, 3) + b"bad"))
        with self.assertRaises(ValueError):
            read_layout(self.file)

    def test_sync_deduplicates_and_keeps_last_good_result_on_decoder_error(self):
        collector = Collector(self.source, data_dir=self.base / "data")
        decoded = {"entities": [], "time_seconds": 1, "diagnostics": {"frames": 1, "movements": 0}}
        with patch("replay_service.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = json.dumps(decoded)
            self.assertTrue(collector.sync())
            previous = collector.last
            self.assertTrue(collector.sync())
            self.assertEqual(run.call_count, 1)
            self.file.write_bytes(replay_bytes(struct.pack("<II", 2, 3) + b"xyz"))
            run.return_value.returncode = 1
            run.return_value.stderr = "Unsupported format"
            self.assertFalse(collector.sync())
            self.assertEqual(collector.last, previous)
            self.assertEqual(json.loads((collector.data_dir / "latest.json").read_text(encoding="utf-8")), previous)
            self.assertEqual(len(list(collector.snapshots.glob("*.replay"))), 1)

    def test_missing_selected_file_does_not_silently_change_source(self):
        collector = Collector(self.source, filename="missing.replay", data_dir=self.base / "data")
        self.assertFalse(collector.sync())
        self.assertIsNone(collector.last)
        self.assertEqual(collector.status["phase"], "error")

    def test_restart_skips_unchanged_source_when_archive_is_retained(self):
        collector=Collector(self.source,data_dir=self.base/'data')
        decoded={'entities':[],'time_seconds':1,'diagnostics':{'frames':1,'movements':0}}
        with patch('replay_service.subprocess.run') as run:
            run.return_value.returncode=0
            run.return_value.stdout=json.dumps(decoded)
            self.assertTrue(collector.sync())
            restarted=Collector(self.source,data_dir=self.base/'data')
            self.assertTrue(restarted.sync())
            self.assertEqual(run.call_count,1,'Restart must not recopy and decode an unchanged multi-GB replay')
            (restarted.history_dir/(restarted.last['id']+'.json.gz')).unlink()
            repaired=Collector(self.source,data_dir=self.base/'data')
            self.assertTrue(repaired.sync())
            self.assertEqual(run.call_count,2,'Missing archive must be regenerated')

    def test_copy_retries_header_change(self):
        import replay_service
        original = replay_service.read_layout
        calls = 0
        def changing(path):
            nonlocal calls
            result = original(path)
            calls += 1
            if calls == 1:
                result["header_bytes"] = b"changed"
            return result
        target = self.base / "snapshot.replay"
        with patch("replay_service.read_layout", changing):
            copy_snapshot(self.file, target)
        self.assertEqual(calls, 2)
        self.assertEqual(target.read_bytes(), self.file.read_bytes())

    def test_background_collector_repeats_without_browser_requests(self):
        collector = Collector(self.source, interval=0.03, data_dir=self.base / "data")
        twice = threading.Event()
        calls = []
        def tick():
            calls.append(1)
            if len(calls) >= 2:
                twice.set()
        with patch.object(collector, "sync", tick):
            collector.start()
            try:
                self.assertTrue(twice.wait(1), "Collector did not automatically run again")
            finally:
                collector.stop.set()
                collector.wake.set()
                collector.thread.join(1)
        self.assertGreaterEqual(len(calls), 2)

    def test_history_preserves_tracks_and_survives_restart(self):
        folder = self.base / "data"
        c = Collector(self.source, data_dir=folder)
        record = {"id": "snapshot-1001", "filename": "demo3.replay", "entities": [{"id": 7}],
                  "tracks": {"7": [[1, 300, 400, 10, 1, 0, .4, 1]]}, "time_seconds": 1}
        c.save_history(record)
        c.last = record
        self.assertNotIn("tracks", c.state()["replay"])
        self.assertNotIn("entities", c.state()["replay"])
        restarted = Collector(self.source, data_dir=folder)
        payload, encoding = restarted.history_payload("snapshot-1001")
        self.assertEqual(encoding, "gzip")
        self.assertEqual(json.loads(gzip.decompress(payload)), record)
        self.assertEqual(len(restarted.state()["history"]), 1)
        self.assertEqual(restarted.history_payload("../../latest"), (None, None))

    def test_history_retention_keeps_newest_50(self):
        c = Collector(self.source, data_dir=self.base / "data")
        for i in range(52):
            c.save_history({"id": f"snapshot-{1000 + i}", "entities": [], "tracks": {}})
        self.assertEqual(len(c.history), 50)
        self.assertEqual(c.history[0]["id"], "snapshot-1051")
        self.assertFalse((c.history_dir / "snapshot-1000.json.gz").exists())
        self.assertTrue((c.history_dir / "snapshot-1051.json.gz").exists())

    def test_fingerprint_is_not_exposed_when_latest_archive_is_missing(self):
        c=Collector(self.source,data_dir=self.base/'data')
        c.last={'id':'snapshot-1001','entities':[],'source_fingerprint':['private-source-path']}
        payload,encoding=c.history_payload('snapshot-1001')
        self.assertIsNone(encoding)
        self.assertNotIn('source_fingerprint',json.loads(payload))
        self.assertNotIn('source_fingerprint',c.state()['replay'])


if __name__ == "__main__":
    unittest.main()
