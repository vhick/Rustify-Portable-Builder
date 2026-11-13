#!/usr/bin/env python3
"""Safe official Rustify ZIP -> PortableApps package + independently validated ZIP.
The shared installer never receives or edits Data: its own behavior preserves Data.
"""
from __future__ import annotations
import argparse, configparser, hashlib, json, os, re, shutil, stat, sys, zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
PACKAGE = Path(os.environ.get('RUSTIFY_STAGE_ROOT', str(WORK / 'RustifyPortable')))
RELEASE = ROOT / 'release-out'
MAX_ENTRIES = 60000
MAX_UNCOMPRESSED = 2 * 1024**3

def sha(path: Path) -> str:
    d = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            d.update(chunk)
    return d.hexdigest()

def is_pe(path: Path, machine: int | None = None) -> bool:
    try:
        with path.open('rb') as f:
            if f.read(2) != b'MZ': return False
            f.seek(0x3c); pe_offset = int.from_bytes(f.read(4), 'little')
            if not 64 <= pe_offset < path.stat().st_size - 6: return False
            f.seek(pe_offset)
            if f.read(4) != b'PE\0\0': return False
            actual = int.from_bytes(f.read(2), 'little')
            return machine is None or actual == machine
    except (OSError, ValueError):
        return False

def safe_unzip(zipped: Path, dest: Path, required_prefix='Rustify/') -> None:
    if not zipfile.is_zipfile(zipped):
        raise ValueError('Upstream ZIP is not a ZIP file')
    count, total = 0, 0
    with zipfile.ZipFile(zipped) as z:
        names = set()
        for info in z.infolist():
            count += 1
            if count > MAX_ENTRIES: raise ValueError('Archive contains too many entries')
            original = info.filename.replace('\\', '/')
            p = PurePosixPath(original)
            if (not original.startswith(required_prefix) or p.is_absolute() or
                any(part in ('..', '.', '') for part in p.parts) or ':' in original or '\x00' in original):
                # The root directory entry Rustify/ is allowed.
                if original.rstrip('/') != required_prefix.rstrip('/'):
                    raise ValueError(f'Unexpected or dangerous upstream path: {original}')
            if original.casefold() in names: raise ValueError(f'Duplicate archive entry: {original}')
            names.add(original.casefold())
            mode = (info.external_attr >> 16) & 0xffff
            if stat.S_IFMT(mode) == stat.S_IFLNK: raise ValueError(f'Symlink in upstream ZIP: {original}')
            total += info.file_size
            if total > MAX_UNCOMPRESSED: raise ValueError('Upstream ZIP expanded size exceeds safety limit')
            dest_path = dest.joinpath(*p.parts)
            if info.is_dir():
                dest_path.mkdir(parents=True, exist_ok=True)
            else:
                if any(x.endswith((':', ' ')) for x in p.parts): raise ValueError(f'Windows unsafe path {original}')
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as reader, dest_path.open('wb') as writer:
                    shutil.copyfileobj(reader, writer, 1024*1024)

def ensure_no_symlinks(root: Path):
    for p in [root, *root.rglob('*')]:
        if p.is_symlink(): raise ValueError(f'Symlink/junction not allowed: {p}')
        if os.name == 'nt' and (getattr(p.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise ValueError(f'Windows reparse point not allowed: {p}')

def metadata(tag: str, version: str) -> str:
    a,b,c = [int(x) for x in version.split('.')]
    if any(x > 65535 for x in (a,b,c)): raise ValueError('Invalid PackageVersion Windows numeric components')
    display = version + (' Beta' if 'beta' in tag.lower() else '')
    return f'''[Format]
Type=PortableApps.comFormat
Version=3.8

[Details]
Name=Rustify Portable (Unofficial)
AppID=RustifyVhickPortable
Publisher=Pablo Soage Rodas (upstream), independent portable packaging
Homepage=https://github.com/PabloSoage/Rustify
Category=Music & Video
Description=Music player with selectable audio backends
Language=Multilingual

[License]
Shareable=true
OpenSource=true
Freeware=true
CommercialUse=true

[Version]
PackageVersion={a}.{b}.{c}.0
DisplayVersion={display}

[Control]
Icons=1
Start=RustifyPortable.exe
'''

def zip_package(stage: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve ALL empty directories, explicitly including nested Data directories.
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for p in sorted(stage.rglob('*')):
            rel = p.relative_to(stage.parent).as_posix()
            if p.is_dir():
                z.writestr(rel + '/', b'')
            elif p.is_file():
                z.write(p, arcname=rel)
            else:
                raise ValueError(f'Nonstandard staging object: {p}')

def build():
    data = json.loads((WORK/'resolution.json').read_text(encoding='utf-8'))
    official_zip = WORK / 'upstream-portable.zip'
    if sha(official_zip) != data['asset']['sha256']: raise ValueError('Upstream source SHA256 no longer matches')
    upstream = WORK/'upstream-extracted'
    if upstream.exists(): shutil.rmtree(upstream)
    safe_unzip(official_zip, upstream)
    original = upstream/'Rustify'
    app_exe = original/'Rustify.exe'
    if not is_pe(app_exe, 0x8664): raise ValueError('Official Rustify.exe is not a Windows x64 PE')
    if not (original/'portable').is_file():
        raise ValueError('Official portable marker missing. This release may not implement portable mode.')
    if not (original/'app').is_dir() or not (original/'runtime').is_dir():
        raise ValueError('Official jpackage app/ and embedded runtime/ are required for standalone operation')
    if not (original/'app'/'Rustify.cfg').is_file():
        raise ValueError('Upstream jpackage app configuration Rustify.cfg missing')
    for binary in ('core_engine.dll', 'rustify-login.exe'):
        matches = list(original.rglob(binary))
        if len(matches) != 1 or not is_pe(matches[0], 0x8664):
            raise ValueError(f'Official Rustify desktop dependency {binary} missing, duplicated or not x64 PE')
    # App may be replaced during a shared-installer upgrade. Never store user data inside it.
    for candidate in ('data','cache'):
        d = original/candidate
        if d.exists() and any(d.iterdir()):
            raise ValueError(f'Unexpected packaged upstream {candidate} contents: review before copying into disposable App')
        if d.exists(): shutil.rmtree(d)
    ensure_no_symlinks(original)
    if PACKAGE.exists(): shutil.rmtree(PACKAGE)
    app = PACKAGE/'App'; info=app/'AppInfo'; other=PACKAGE/'Other'/'Source'
    info.mkdir(parents=True)
    other.mkdir(parents=True)
    (PACKAGE/'Data'/'RustifyProfile'/'data'/'settings').mkdir(parents=True)
    (PACKAGE/'Data'/'RustifyProfile'/'cache').mkdir(parents=True)
    shutil.copytree(original, app/'Rustify')
    launcher = WORK/'RustifyPortable.exe'
    if not is_pe(launcher, 0x8664): raise ValueError('Launcher missing or not real x64 Windows PE')
    shutil.copy2(launcher, PACKAGE/'RustifyPortable.exe')
    (info/'appinfo.ini').write_text(metadata(data['tag'], data['version']), encoding='utf-8')
    for icon in ('appicon.ico','appicon_16.png','appicon_32.png'):
        shutil.copy2(ROOT/'assets'/icon, info/icon)
    shutil.copy2(WORK/'source-evidence'/'LICENSE', other/'LICENSE-UPSTREAM-GPL-3.0.txt')
    shutil.copy2(ROOT/'docs'/'PORTABILITY.md', other/'PORTABILITY.md')
    (other/'BUILD-IDENTITY.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    (other/'LAUNCHER-SOURCE-LOCATION.txt').write_text('Launcher source is available in the builder repository: launcher/RustifyPortable.cpp\nGPL-3.0-or-later. No runtime host cleanup is performed.\n', encoding='utf-8')
    # Stage validated below, BEFORE any installer invocation.
    validate_stage(PACKAGE)
    RELEASE.mkdir(exist_ok=True)
    filename = f"RustifyPortable_{data['tag']}_b1r1.zip"
    archive = RELEASE/filename
    if archive.exists(): raise ValueError('Refusing to overwrite ZIP')
    zip_package(PACKAGE, archive)
    validate_zip(archive)
    checksum=sha(archive)
    (WORK/'zip-sha256.txt').write_text(checksum+'  '+filename+'\n', encoding='ascii')
    tag = data.get('candidate_release_tag') or f"portable-rustify-{data['tag']}-b1r1-{data['commit'][:8]}-{data['asset']['sha256'][:8]}-{data['builder_commit'][:8]}"
    if len(tag)>151: raise ValueError('Release tag exceeds publisher maximum')
    outputs = {'zip': str(archive.resolve()), 'sha256': checksum, 'release_tag': tag, 'version': data['version'], 'stage_dir': str(PACKAGE.resolve())}
    (WORK/'stage-result.json').write_text(json.dumps(outputs,indent=2)+'\n', encoding='utf-8')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
            for k,v in outputs.items(): out.write(f'{k}={v}\n')
    print('STATIC-VALIDATED ZIP:', archive, 'sha256:', checksum)

def validate_stage(stage: Path):
    ensure_no_symlinks(stage)
    required = (
        'RustifyPortable.exe', 'App/Rustify/Rustify.exe', 'App/Rustify/portable',
        'App/Rustify/app/Rustify.cfg', 'App/Rustify/runtime',
        'App/AppInfo/appinfo.ini', 'App/AppInfo/appicon.ico', 'App/AppInfo/appicon_16.png',
        'App/AppInfo/appicon_32.png', 'Other/Source/LICENSE-UPSTREAM-GPL-3.0.txt',
        'Data/RustifyProfile/data/settings', 'Data/RustifyProfile/cache'
    )
    for item in required:
        if not (stage/item).exists(): raise ValueError(f'Missing staged file/directory: {item}')
    if not is_pe(stage/'RustifyPortable.exe', 0x8664): raise ValueError('Invalid launcher PE x64')
    if not is_pe(stage/'App'/'Rustify'/'Rustify.exe', 0x8664): raise ValueError('Invalid upstream application PE x64')
    config=configparser.ConfigParser(interpolation=None)
    config.read(stage/'App'/'AppInfo'/'appinfo.ini', encoding='utf-8')
    if config['Format']['Type'] != 'PortableApps.comFormat': raise ValueError('Wrong format')
    if config['Control']['Start'] != 'RustifyPortable.exe': raise ValueError('Wrong launcher')
    if config['Details']['AppID'] != 'RustifyVhickPortable': raise ValueError('Wrong app identity')
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', config['Version']['PackageVersion']):
        raise ValueError('Non-numeric package version')
    if any((stage/'Data').rglob('*')):
        if any(p.is_file() for p in (stage/'Data').rglob('*')):
            raise ValueError('Data contains bundled files; new installs must start blank')

def validate_zip(zfile: Path):
    if not zipfile.is_zipfile(zfile): raise ValueError('Invalid output ZIP')
    with zipfile.ZipFile(zfile) as z:
        if z.testzip() is not None: raise ValueError('Corrupt ZIP entry')
        names = set(z.namelist())
        for name in (
            'RustifyPortable/RustifyPortable.exe',
            'RustifyPortable/App/Rustify/Rustify.exe',
            'RustifyPortable/App/AppInfo/appinfo.ini',
            'RustifyPortable/Data/RustifyProfile/data/settings/',
            'RustifyPortable/Data/RustifyProfile/cache/',
            'RustifyPortable/Other/Source/BUILD-IDENTITY.json'):
            if name not in names: raise ValueError(f'Missing ZIP member: {name}')
        with z.open('RustifyPortable/RustifyPortable.exe') as f:
            if f.read(2) != b'MZ': raise ValueError('ZIP root launcher is not a compiled EXE')

def validate_installer(path: Path):
    if not path.name.lower().endswith('.paf.exe') or not is_pe(path):
        raise ValueError('Installer must be a valid .paf.exe PE (NSIS may be x86 despite x64 app)')
    print('STATIC-VALIDATED installer PE, sha256:', sha(path))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('build','stage','zip','installer'))
    ap.add_argument('--path', default='')
    args=ap.parse_args()
    if args.cmd=='build': build()
    elif args.cmd=='stage': validate_stage(Path(args.path or PACKAGE)); print('STATIC-VALIDATED staging')
    elif args.cmd=='zip': validate_zip(Path(args.path)); print('STATIC-VALIDATED ZIP')
    elif args.cmd=='installer': validate_installer(Path(args.path))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
