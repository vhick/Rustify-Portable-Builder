#!/usr/bin/env python3
"""Before downloading a 100+ MB app, avoid rebuilding an identical publisher-managed release."""
import json, os, re, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

def main():
    r = json.loads(Path('work/resolution.json').read_text(encoding='utf-8'))
    tag = r['candidate_release_tag']
    repo = os.environ['GITHUB_REPOSITORY']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid calling GitHub repository')
    url = 'https://api.github.com/repos/' + repo + '/releases/tags/' + urllib.parse.quote(tag, safe='')
    headers = {'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'RustifyPortableBuilder-b1r1'}
    if os.getenv('GH_TOKEN'): headers['Authorization']='Bearer ' + os.environ['GH_TOKEN']
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=40) as response:
            release=json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code==404:
            release=None
        else:
            raise RuntimeError(f'Existing release lookup HTTP {exc.code}; refusing to assume absent') from exc
    skip=release is not None
    if skip:
        body=release.get('body') or ''
        assets={a.get('name','') for a in release.get('assets',[])}
        expected=f"RustifyPortable_{r['tag']}_b1r1.zip"
        if release.get('draft') or '<!-- portable-release-publisher:managed:v2 -->' not in body:
            raise RuntimeError('Release tag exists but was not safely publisher-managed; refusing overwrite')
        if expected not in assets or 'SHA256SUMS.txt' not in assets:
            raise RuntimeError('Matching identity release exists but is incomplete; inspect manually before running')
        print('Same publisher-managed release already exists; duplicate build/download skipped:',tag)
    else:
        print('No matching build yet; proceed with download, compilation and packaging:',tag)
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:
            out.write(f"skip={'true' if skip else 'false'}\n")

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('ERROR:',exc,file=sys.stderr)
        sys.exit(1)
