import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import replay_service as app


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.root_patch=patch.object(app,'ROOT',self.root)
        self.root_patch.start()
        self.data=self.root/'data'

    def tearDown(self):
        self.root_patch.stop()
        self.tmp.cleanup()

    def test_fresh_install_has_no_baked_in_account(self):
        self.assertEqual(app.load_player_profile(self.data),{'steam_id':'','name':''})

    def test_arbitrary_id_round_trip_clear_and_legacy_migration(self):
        legacy=self.root/'web/assets/player-profile.json'
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({'steam_id':'76561198000000123','name':'Original'}))
        self.assertTrue(app.load_player_profile(self.data)['migrated_legacy'])
        app.save_player_profile(self.data,{'steam_id':'76561198000000456','name':'New account'})
        self.assertEqual(app.load_player_profile(self.data)['steam_id'],'76561198000000456')
        app.save_player_profile(self.data,{'steam_id':'','name':'Unused'})
        self.assertEqual(app.load_player_profile(self.data)['steam_id'],'','Explicit clear must not remigrate the old account')

    def test_id_must_remain_a_17_digit_string(self):
        for value in [12345678901234567,'short','7656119800000000x',None,1.2345,{},'７'*17]:
            with self.assertRaises(ValueError):
                app.save_player_profile(self.data,{'steam_id':value})
        with self.assertRaises(ValueError):
            app.save_player_profile(self.data,{'steam_id':'76561198000000001','name':'x'*61})

    def test_ui_revision_reads_unchanged_assets_only_once(self):
        for name in app.UI_ASSETS:
            p=self.root/'web'/name
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text('initial')
        original=Path.read_bytes
        reads=[]
        def read(path):
            reads.append(path)
            return original(path)
        with patch.object(Path,'read_bytes',read):
            first=app.ui_revision()
            self.assertEqual(first,app.ui_revision())
            self.assertEqual(len(reads),len(app.UI_ASSETS))
            app.save_player_profile(self.data,{'steam_id':'76561198000000001'})
            self.assertEqual(first,app.ui_revision(),'Profile changes do not force a page reload')
            (self.root/'web/app.js').write_text('new version with different bytes')
            self.assertNotEqual(first,app.ui_revision())

    def test_profile_api_validation_persistence_and_local_origin(self):
        collector=app.Collector(self.root/'source',data_dir=self.data)
        server=app.LocalServer(('127.0.0.1',0),app.Handler)
        server.collector=collector
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def post(payload,headers=None):
            h={'Content-Type':'application/json','X-Isle-Client':'1','Origin':base} if headers is None else headers
            return urllib.request.urlopen(urllib.request.Request(base+'/api/profile',json.dumps(payload).encode(),headers=h))
        try:
            with urllib.request.urlopen(base+'/api/profile') as response:
                self.assertEqual(json.load(response)['steam_id'],'')
            with post({'steam_id':'76561198000000123','name':'Independent'}) as response:
                self.assertEqual(json.load(response)['steam_id'],'76561198000000123')
            for payload in [{'steam_id':76561198000000123},[],{'steam_id':'bad'}]:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    post(payload)
                self.assertEqual(error.exception.code,400)
            with self.assertRaises(urllib.error.HTTPError) as error:
                post({'steam_id':''},headers={'Content-Type':'application/json'})
            self.assertEqual(error.exception.code,403)
            self.assertEqual(collector.state()['player_profile']['name'],'Independent')
        finally:
            server.shutdown();server.server_close();worker.join()


if __name__=='__main__':
    unittest.main()
