"""Verify the script-only distribution in a relocated, empty-profile environment."""
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
    parser.add_argument('--archive',type=Path,default=ROOT/'dist/VMconsole-win-x64.zip')
    parser.add_argument('--port',type=int,default=8767)
    parser.add_argument('--work-dir',type=Path,default=ROOT/'qa')
    options=parser.parse_args()
    url=f'http://127.0.0.1:{options.port}'
    qa=options.work_dir.resolve()
    qa.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vmconsole-',dir=qa) as temp:
        base=Path(temp).resolve()
        assert base.is_relative_to(qa)
        with zipfile.ZipFile(options.archive) as z:
            assert all('..' not in Path(p).parts and not Path(p).is_absolute() for p in z.namelist())
            assert not any(Path(p).name.startswith('ReplayRadar') and Path(p).suffix=='.exe' for p in z.namelist())
            assert not any(Path(p).name in ('config.json','player-profile.json','VMconsole.settings.json') for p in z.namelist())
            z.extractall(base/'Máy khác')
        app=base/'Máy khác/VMconsole-win-x64'
        assert not list(app.glob('*.exe')),'No custom application executable should be required'
        data=base/'data'
        source=base/'source replays'
        source.mkdir()
        shutil.copy2(ROOT.parent/'demo3.replay',source/'demo.replay')
        copies=base/'private copies'
        env=os.environ.copy()
        env.update(PATH=str(Path(env['WINDIR'])/'System32'),LOCALAPPDATA=str(base/'empty-profile'),PYTHONUTF8='1',DOTNET_ROOT=str(app/'runtime/dotnet'))
        for executable in ('python','dotnet'):
            assert shutil.which(executable,path=env['PATH']) is None
        powershell=Path(env['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        command=[str(powershell),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(app/'VMconsole.ps1'),
                 '-DataDirectory',str(data),'-SourceFolder',str(source),'-ReplayFile','demo.replay','-CopyFolder',str(copies),'-Port',str(options.port),'-NonInteractive']
        def get(path):
            with urllib.request.urlopen(url+path,timeout=3) as response:
                b=response.read()
                return json.loads(gzip.decompress(b) if response.headers.get('Content-Encoding')=='gzip' else b)
        def launch():
            log=(base/'console.log').open('wb')
            parent=subprocess.Popen(command,env=env,cwd=app,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            end=time.monotonic()+35
            while time.monotonic()<end:
                if parent.poll() is not None:
                    log.close()
                    raise AssertionError((base/'console.log').read_text(encoding='utf8',errors='replace'))
                try:
                    s=get('/api/state')
                    if s['status']['phase']=='error':raise AssertionError(s['status']['error'])
                    if s['status']['phase']=='idle' and s['replay']:return parent,log,s
                except OSError:pass
                time.sleep(.2)
            parent.kill();parent.wait();log.close()
            raise AssertionError('VMconsole did not become ready: '+(base/'console.log').read_text(encoding='utf8',errors='replace'))
        parent=None
        try:
            parent,log,state=launch()
            assert get('/api/health')['service_root']==str(app)
            assert state['source_dir']==str(source)
            assert state['selected_file']=='demo.replay'
            assert state['copy_dir']==str(copies)
            replay=get('/api/replays/'+state['replay']['id'])
            assert replay['diagnostics']['failed_movements']==0
            assert replay['diagnostics']['frames']==10728
            assert not state['player_profile']['steam_id']
            snapshot=state['replay']['id']
            parent.kill();parent.wait(timeout=5);log.close();parent=None
            end=time.monotonic()+5
            while time.monotonic()<end:
                try:get('/api/health')
                except OSError:break
                time.sleep(.1)
            else:raise AssertionError('Closing the console must close its backend')
            parent,log,restored=launch()
            assert restored['replay']['id']==snapshot
            print(json.dumps({'script_only':True,'relocated_unicode_path':True,'system_runtimes_absent':True,'frames':10728,'movement_errors':0,'private_copy_folder':True,'console_close_cleanup':True,'restart_reuses_snapshot':True}))
        finally:
            if parent and parent.poll() is None:
                parent.kill();parent.wait(timeout=5);log.close()
                time.sleep(.3)


if __name__=='__main__':main()
