"""Build a portable Windows x64 ZIP from an explicit, non-personal allowlist."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import argparse

ROOT = Path(__file__).resolve().parent
FILES = ('replay_service.py','telegram_alerts.py','runtime.ps1','launch.ps1','service.ps1','setup.ps1','bootstrap-python.ps1',
         'start.cmd','stop.cmd','doctor.ps1','check.cmd','README.md','PORTABLE.md','MAP-SOURCES.md','VITALS-SOURCES.md','TELEGRAM.md','EFFECTS-SOURCES.md')


def build(web_root=None, windows_service=False, console_script=False, output_dir=None):
    if windows_service and console_script:
        raise ValueError('Choose one distribution mode.')
    output = Path(output_dir).resolve() if output_dir else ROOT / 'dist'
    output.mkdir(parents=True, exist_ok=True)
    folder = output / ('VMconsole-win-x64' if console_script else 'ReplayRadar-Service-win-x64' if windows_service else 'ReplayRadar-win-x64')
    # Refuse to merge a stale release tree, which might contain a user's settings.
    if folder.exists():
        raise FileExistsError('Release folder already exists. Choose a clean dist directory before rebuilding.')
    folder.mkdir()
    files = ('replay_service.py','telegram_alerts.py','ReplayRadar.exe','ReplayRadar.Service.exe','ReplayRadar.exe.config','ReplayRadar.Service.exe.config','WINDOWS-SERVICE.md','MAP-SOURCES.md','VITALS-SOURCES.md','TELEGRAM.md','EFFECTS-SOURCES.md') if windows_service else FILES
    if console_script:
        files = ('VMconsole.cmd','VMconsole.ps1','runtime.ps1','replay_service.py','telegram_alerts.py','MAP-SOURCES.md','VITALS-SOURCES.md','TELEGRAM.md','EFFECTS-SOURCES.md')
    for name in files:
        shutil.copy2(ROOT / name, folder / name)
    shutil.copytree(web_root or ROOT / 'web', folder / 'web', ignore=shutil.ignore_patterns('player-profile.json'))
    for name in ('IsleDecoder.dll','IsleDecoder.deps.json','IsleDecoder.runtimeconfig.json'):
        target = folder / 'decoder/bin' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'decoder/bin' / name, target)
    shutil.copytree(ROOT / 'runtime/python', folder / 'runtime/python', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    dotnet = ROOT / 'runtime/dotnet'
    for name in ('dotnet.exe','LICENSE.txt','ThirdPartyNotices.txt'):
        target = folder / 'runtime/dotnet' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dotnet / name, target)
    versions = {}
    for name in ('host/fxr','shared/Microsoft.NETCore.App','shared/Microsoft.AspNetCore.App'):
        version = max((p for p in (dotnet / name).iterdir() if p.is_dir() and p.name.startswith('10.')), key=lambda p:tuple(map(int,p.name.split('.'))))
        shutil.copytree(version, folder / 'runtime/dotnet' / name / version.name)
        versions[name] = version.name
    (folder / 'licenses').mkdir()
    shutil.copy2(ROOT / 'vendor/UNREAL-LICENSE.txt', folder / 'licenses/UNREAL-LICENSE.txt')
    (folder / 'portable-info.json').write_text(json.dumps({'platform':'win-x64','dotnet':versions,
        'python':'3.14.10','python_source':'https://www.python.org/downloads/release/python-31410/',
        'python_zip_sha256':'90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159',
        'contains_user_data':False,'windows_service':windows_service,'console_script':console_script,'requires_administrator_to_install':windows_service},indent=2),encoding='utf8')
    forbidden = [p for p in folder.rglob('*') if p.name in ('config.json','player-profile.json') or p.suffix == '.replay' or p.name in ('data','qa','sdk','packs')]
    if forbidden:
        raise ValueError(f'Non-portable content detected: {forbidden}')
    archive = output / (folder.name + '.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():
                z.write(p,p.relative_to(output))
    with archive.open('rb') as source:
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
        checksum = digest.hexdigest()
    archive.with_suffix('.zip.sha256').write_text(checksum+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':checksum}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--web-root',type=Path)
    parser.add_argument('--windows-service',action='store_true')
    parser.add_argument('--console-script',action='store_true')
    parser.add_argument('--output-dir',type=Path,help='Build into a new release directory without replacing an existing package.')
    args=parser.parse_args()
    build(args.web_root,args.windows_service,args.console_script,args.output_dir)
