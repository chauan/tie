import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import replay_service as app
from test_service import replay_bytes


class CopyWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.dotnet_lookup = patch('replay_service.shutil.which', return_value='dotnet-test')
        self.dotnet_lookup.start()
        self.addCleanup(self.dotnet_lookup.stop)
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.source=self.base/'LocalAppData/TheIsle/Saved/Demos'
        self.source.mkdir(parents=True)
        self.file=self.source/'demo.replay'
        self.file.write_bytes(replay_bytes())
        self.copies=self.base/'Private Scan'

    def tearDown(self):
        self.tmp.cleanup()

    def test_layout_and_decoder_only_receive_copies_in_selected_workspace(self):
        c=app.Collector(self.source,filename='demo.replay',data_dir=self.base/'data',copy_dir=self.copies)
        original=self.file.read_bytes()
        seen=[]
        layout=app.read_layout
        def inspect(path):
            path=Path(path).resolve()
            self.assertTrue(path.is_relative_to(self.copies))
            self.assertFalse(path.is_relative_to(self.source))
            seen.append(path)
            return layout(path)
        def decode(args,**kwargs):
            replay=Path(args[-1]).resolve()
            self.assertEqual(replay.parent,self.copies)
            self.assertEqual(replay.read_bytes(),original)
            return __import__('subprocess').CompletedProcess(args,0,json.dumps({'entities':[],'time_seconds':1,'diagnostics':{'frames':1,'movements':0}}),'')
        with patch('replay_service.read_layout',inspect),patch('replay_service.subprocess.run',decode):
            self.assertTrue(c.sync())
        self.assertTrue(seen)
        self.assertEqual(self.file.read_bytes(),original)
        self.assertEqual(c.state()['copy_dir'],str(self.copies))

    def test_source_and_workspace_cannot_overlap(self):
        for copy in (self.source,self.source/'copies',self.source.parent):
            with self.assertRaises(ValueError):
                app.prepare_copy_directory(self.source,copy)
        self.assertEqual(app.prepare_copy_directory(self.source,self.copies),self.copies)

    def test_switching_copy_directory_requires_a_new_copy(self):
        def decode(args,**kwargs):
            return __import__('subprocess').CompletedProcess(args,0,json.dumps({'entities':[],'time_seconds':1,'diagnostics':{'frames':1,'movements':0}}),'')
        with patch('replay_service.subprocess.run',decode):
            c=app.Collector(self.source,data_dir=self.base/'data',copy_dir=self.copies)
            self.assertTrue(c.sync())
            old=c.last['id']
            second=app.Collector(self.source,data_dir=self.base/'data',copy_dir=self.base/'Second Scan')
            self.assertTrue(second.sync())
            self.assertNotEqual(old,second.last['id'])

    def test_deleted_copy_is_regenerated_even_if_original_is_unchanged(self):
        with patch('replay_service.subprocess.run') as run:
            run.return_value.returncode=0
            run.return_value.stdout=json.dumps({'entities':[],'time_seconds':1,'diagnostics':{'frames':1,'movements':0}})
            c=app.Collector(self.source,data_dir=self.base/'data',copy_dir=self.copies)
            self.assertTrue(c.sync())
            (self.copies/(c.last['id']+'.replay')).unlink()
            self.assertTrue(c.sync())
            self.assertEqual(run.call_count,2)

    def test_retention_does_not_delete_other_files_in_the_workspace(self):
        c=app.Collector(self.source,data_dir=self.base/'data',copy_dir=self.copies)
        other=self.copies/'snapshot-999.replay'
        other.write_bytes(b'not created by this collector')
        with patch('replay_service.subprocess.run') as run:
            run.return_value.returncode=0
            run.return_value.stdout=json.dumps({'entities':[],'time_seconds':1,'diagnostics':{'frames':1,'movements':0}})
            for i in range(5):
                c.fingerprint=None
                self.assertTrue(c.sync())
        self.assertEqual(other.read_bytes(),b'not created by this collector')
        self.assertEqual(len(list(self.copies.glob('snapshot-*.replay'))),4)
        self.assertEqual(len(json.loads((self.copies/'.replay-radar-workspace.json').read_text())['files']),3)


if __name__=='__main__':unittest.main()
