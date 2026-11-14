"""Exercise the real service host without registering a privileged OS service."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ROOT/'dist/ReplayRadar-Service-win-x64.zip')
    parser.add_argument('--port',type=int,default=8767)
    parser.add_argument('--work-dir',type=Path,default=ROOT/'qa')
    options=parser.parse_args()
    url=f'http://127.0.0.1:{options.port}'
    qa=options.work_dir.resolve()
    qa.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='service-host-',dir=qa) as temporary:
        base=Path(temporary).resolve()
        assert base.is_relative_to(qa)
        data=base/'Dữ liệu service'
        data.mkdir()
        source=base/'replays'
        source.mkdir()
        shutil.copy2(ROOT.parent/'demo3.replay',source/'fixture.replay')
        bundle=ROOT
        package=options.archive
        if package.exists():
            with zipfile.ZipFile(package) as z:
                assert not any(Path(p).suffix.lower() in ('.cmd','.bat','.ps1') for p in z.namelist()),'GUI service distribution must not require shell launchers'
                assert not any(Path(p).name in ('config.json','player-profile.json') or p.endswith('.replay') for p in z.namelist())
                assert all('..' not in Path(p).parts and not Path(p).is_absolute() for p in z.namelist())
                z.extractall(base/'Gói service')
            bundle=base/'Gói service/ReplayRadar-Service-win-x64'
        copies=base/'Private replay scan'
        (data/'config.json').write_text(json.dumps({'source_dir':str(source),'filename':'fixture.replay','copy_dir':str(copies),'interval_seconds':180}),encoding='utf8')
        stop=data/'probe-stop'
        args=[str(bundle/'ReplayRadar.Service.exe'),'--probe','--app-root',str(bundle),'--data-dir',str(data),'--port',str(options.port)]

        def get(path):
            with urllib.request.urlopen(url+path,timeout=3) as r:
                b=r.read()
                return json.loads(gzip.decompress(b) if r.headers.get('Content-Encoding')=='gzip' else b)

        def alive(pid):
            import ctypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.restype=ctypes.c_void_p
            kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            handle=kernel.OpenProcess(0x1000,False,pid)
            if not handle:return False
            code=ctypes.c_ulong()
            try:return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
            finally:kernel.CloseHandle(handle)

        def launch():
            for name in ('probe-ready.json','probe-stopped.json','probe-error.txt','probe-stop'):
                (data/name).unlink(missing_ok=True)
            process=subprocess.Popen(args,creationflags=subprocess.CREATE_NO_WINDOW)
            end=time.monotonic()+18
            while time.monotonic()<end:
                if (data/'probe-error.txt').exists():raise AssertionError((data/'probe-error.txt').read_text())
                if (data/'probe-ready.json').exists():return process,json.loads((data/'probe-ready.json').read_text())['pid']
                assert process.poll() is None,'Service host exited before readiness'
                time.sleep(.1)
            process.kill();process.wait()
            raise AssertionError('Host readiness timeout')

        host,pid=launch()
        try:
            end=time.monotonic()+20
            while time.monotonic()<end:
                state=get('/api/state')
                if state['status']['phase']=='idle':break
                assert state['status']['phase']!='error',state['status']['error']
                time.sleep(.1)
            assert state['source_dir']==str(source),'Service must use its explicit data folder, not the interactive profile config'
            assert state['status']['phase']=='idle'
            assert state['copy_dir']==str(copies)
            assert list(copies.glob('snapshot-*.replay'))
            assert str(copies) in (data/'service.log').read_text(encoding='utf8')
            if bundle!=ROOT:
                assert not state['player_profile']['steam_id'],'Fresh GUI service package must not contain a selected account'
            replay=get('/api/replays/'+state['replay']['id'])
            assert replay['diagnostics']['failed_movements']==0
            # Config API must persist outside the protected program directory.
            req=urllib.request.Request(url+'/api/config',json.dumps({'source_dir':str(source),'filename':'fixture.replay'}).encode(),headers={'Content-Type':'application/json','X-Isle-Client':'1'})
            with urllib.request.urlopen(req):pass
            assert json.loads((data/'config.json').read_text(encoding='utf8'))['filename']=='fixture.replay'
            stop.touch()
            assert host.wait(timeout=15)==0
            assert not alive(pid),'Graceful stop must close the owned backend'
            assert (data/'probe-stopped.json').exists()
            host,pid=launch()
            host.kill();host.wait(timeout=5)
            end=time.monotonic()+5
            while time.monotonic()<end and alive(pid):time.sleep(.1)
            assert not alive(pid),'Job cleanup must close backend when host is terminated'
            print(json.dumps({'native_host':True,'replay_frames':replay['diagnostics']['frames'],'movement_errors':0,
                              'external_data_config':True,'graceful_stop':True,'job_cleanup':True,'gui_only_package':bundle!=ROOT,'scm_registration_tested':False}))
        finally:
            if host.poll() is None:
                stop.touch()
                try:host.wait(timeout=15)
                except subprocess.TimeoutExpired:host.kill();host.wait()


if __name__=='__main__':main()
