#!/usr/bin/env python3
"""Download ONLY the pinned GitHub release asset, then compare SHA256 digest."""
import hashlib, json, pathlib, sys, urllib.request

record = json.loads(pathlib.Path('work/resolution.json').read_text(encoding='utf-8'))
a = record['asset']
output = pathlib.Path('work/upstream-portable.zip')
output.parent.mkdir(parents=True, exist_ok=True)
req = urllib.request.Request(a['url'], headers={'User-Agent':'RustifyPortableBuilder-b1r2'})
h = hashlib.sha256()
size = 0
try:
    with urllib.request.urlopen(req, timeout=180) as src, output.with_suffix('.partial').open('wb') as dst:
        while True:
            data=src.read(1024*1024)
            if not data: break
            size += len(data)
            if size > 2_000_000_000: raise ValueError('Unreasonably large asset')
            dst.write(data)
            h.update(data)
    if h.hexdigest() != a['sha256'] or (a['size'] and size != a['size']):
        raise ValueError('Official asset digest or byte length mismatch; download rejected')
    output.with_suffix('.partial').replace(output)
except Exception:
    output.with_suffix('.partial').unlink(missing_ok=True)
    raise
print(f"Verified official download: {size} bytes, sha256:{h.hexdigest()}")
