#!/usr/bin/env python3
"""Reinstall the same validated ZIP into staging for a new installer-only release.
Requires a publisher-managed release's SHA256SUMS.txt, never accepts an unverified ZIP.
"""
import argparse, hashlib, json, os, re, shutil, sys
from pathlib import Path
from stage import safe_unzip, validate_stage, sha

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--directory',default='work/source-repack')
    args=p.parse_args()
    directory=Path(args.directory)
    sums=(directory/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
    zips=list(directory.glob('RustifyPortable_*.zip'))
    if len(zips)!=1: raise ValueError('Expected one original RustifyPortable_*.zip in managed release')
    z=zips[0]
    expected=[]
    for line in sums:
        match=re.fullmatch(r'([0-9a-fA-F]{64})  (.+)',line)
        if not match: raise ValueError('Invalid publisher checksum manifest')
        if match.group(2)==z.name: expected.append(match.group(1).lower())
    if len(expected)!=1 or sha(z)!=expected[0]:
        raise ValueError('Source ZIP SHA256 does not match release checksum!')
    dst=Path('work')
    package=dst/'RustifyPortable'
    if package.exists(): shutil.rmtree(package)
    safe_unzip(z,dst,'RustifyPortable/')
    validate_stage(package)
    manifest=json.loads((package/'Other/Source/BUILD-IDENTITY.json').read_text(encoding='utf-8'))
    if manifest.get('repository')!='PabloSoage/Rustify' or manifest.get('builder_revision')!='b1r1':
        raise ValueError('Source ZIP is not built by this kit; provenance rejected')
    builder=os.environ.get('GITHUB_SHA','local')[:8]
    release_tag=f'portable-rustify-repack-{sha(z)[:12]}-r2-{builder}'
    result={'release_tag':release_tag,'version':manifest['version'],'source_zip_sha256':sha(z)}
    Path('work/repackage-result.json').write_text(json.dumps(result,indent=2)+'\n', encoding='utf-8')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:
            for k,v in result.items(): out.write(f'{k}={v}\n')
    print('Original ZIP verified against publisher checksum, staging verified, output tag:',release_tag)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('ERROR:',exc,file=sys.stderr)
        sys.exit(1)
