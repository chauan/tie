"""Relocate the actual ZIP, use an empty Windows profile and no system runtimes."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
import uuid

def main():
    ROOT=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ROOT/'dist/ReplayRadar-win-x64.zip')
    parser.add_argument('--port',type=int,default=8767)
    parser.add_argument('--work-dir',type=Path,default=ROOT/'qa')
    args=parser.parse_args()
    PORT=args.port
    BASE=f'http://127.0.0.1:{PORT}'
    QA=args.work_dir.resolve()
    QA.mkdir(parents=True,exist_ok=True)
    temp=tempfile.TemporaryDirectory(prefix='portable-',dir=QA)
    assert Path(temp.name).resolve().is_relative_to(QA)
    destination=Path(temp.name)/'Máy khác space'
    destination.mkdir()
    archive=args.archive
    with zipfile.ZipFile(archive) as z:
        assert all('..' not in Path(p).parts and not Path(p).is_absolute() for p in z.namelist())
        assert not any(Path(p).name in ('config.json','player-profile.json') or p.endswith('.replay') for p in z.namelist())
        z.extractall(destination)
    app=destination/'ReplayRadar-win-x64'
    env=os.environ.copy()
    env.update(PATH=str(Path(os.environ['WINDIR'])/'System32'),LOCALAPPDATA=str(Path(temp.name)/'empty-profile/Local'),
               PYTHONUTF8='1',DOTNET_ROOT=str(app/'runtime/dotnet'),DOTNET_MULTILEVEL_LOOKUP='0')
    source=Path(env['LOCALAPPDATA'])/'TheIsle/Saved/Demos'
    source.mkdir(parents=True)
    shutil.copy2(ROOT.parent/'demo3.replay',source/'portable-demo.replay')
    ps=Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    started=False


    def shell(script,*args):
        log=Path(temp.name)/(str(uuid.uuid4())+'.log')
        with log.open('wb') as output:
            result=subprocess.run([str(ps),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(app/script),*args],
                                  cwd=app,env=env,stdout=output,stderr=subprocess.STDOUT,
                                  timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==0,log.read_text(encoding='utf8',errors='replace')
        return result


    def get(path):
        with urllib.request.urlopen(BASE+path,timeout=5) as response:
            data=response.read()
            if response.headers.get('Content-Encoding')=='gzip':
                data=gzip.decompress(data)
            return json.loads(data)


    def ready():
        end=time.monotonic()+45
        while time.monotonic()<end:
            state=get('/api/state')
            if state['status']['phase']=='error':
                raise AssertionError(state['status']['error'])
            if state['status']['phase']=='idle' and state['replay']:
                return state
            time.sleep(.2)
        raise AssertionError('Portable collector timed out')


    try:
        for executable in ('python','dotnet'):
            assert shutil.which(executable,path=env['PATH']) is None
        shell('doctor.ps1')
        print('portable: bundled dependencies checked',flush=True)
        shell('service.ps1','-Action','Start','-Port',str(PORT))
        started=True
        state=ready()
        print('portable: actual replay decoded in relocated package',flush=True)
        assert get('/api/health')['service_root']==str(app)
        assert state['source_dir']==str(source.resolve()),'Must detect the destination Windows profile'
        assert state['player_profile']['steam_id']=='','Fresh package must not inherit the builder account'
        decoded=get('/api/replays/'+state['replay']['id'])
        assert decoded['diagnostics']['failed_movements']==0
        players=[e for e in decoded['entities'] if e['kind']=='player' and e.get('steam_id') and e.get('in_scope') and not e.get('dead')]
        assert players
        picked=players[-1]
        payload=json.dumps({'steam_id':picked['steam_id'],'name':'Portable account'}).encode()
        req=urllib.request.Request(BASE+'/api/profile',payload,headers={'Content-Type':'application/json','X-Isle-Client':'1','Origin':BASE})
        with urllib.request.urlopen(req) as response:
            assert json.load(response)['steam_id']==picked['steam_id']
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
            page=browser.new_page()
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(BASE,wait_until='networkidle')
            page.wait_for_function("() => typeof currentProximity==='function' && currentProximity().available")
            assert page.evaluate('playerProfile.steam_id')==picked['steam_id']
            assert page.evaluate('currentProximity().owner.steam_id')==picked['steam_id']
            assert not errors,errors
            browser.close()
        snapshot=state['replay']['id']
        shell('service.ps1','-Action','Stop','-Port',str(PORT))
        started=False
        shell('service.ps1','-Action','Start','-Port',str(PORT))
        started=True
        restored=ready()
        assert restored['replay']['id']==snapshot,'Restart must reuse the unchanged replay snapshot'
        assert restored['player_profile']['steam_id']==picked['steam_id']
        print(json.dumps({'relocated_unicode_path':True,'empty_windows_profile':True,'system_python_dotnet_absent':True,
                          'decoder_frames':decoded['diagnostics']['frames'],'failed_movements':0,'configurable_account':True,
                          'profile_persisted':True,'restart_reuses_snapshot':True,'javascript_errors':errors}))
    finally:
        try:
            if get('/api/health')['service_root']==str(app):
                shell('service.ps1','-Action','Stop','-Port',str(PORT))
        except OSError:
            pass
        temp.cleanup()


if __name__=='__main__':
    main()
