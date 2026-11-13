#!/usr/bin/env python3
"""Resolve a published official Rustify Windows portable asset; never compile main.
Production security: GitHub release API asset digest REQUIRED, tag commit resolved,
source portability evidence checked at the exact tag commit.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

REPO = "PabloSoage/Rustify"
API = f"https://api.github.com/repos/{REPO}"
APP_ASSET = re.compile(r"^Rustify-.+-windows-x86_64-portable\.zip$", re.I)
VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-.](alpha|beta|b|rc)(?:[.-]?(\d+))?)?$", re.I)
PORTABILITY_SOURCES = {
    "AppDirs.kt": ("shared/src/desktopMain/kotlin/com/varuna/rustify/platform/AppDirs.kt", ("RUSTIFY_PORTABLE_DIR", "portableRoot", 'File(it, "data")', 'File(it, "cache")')),
    "DesktopStores.kt": ("shared/src/desktopMain/kotlin/com/varuna/rustify/platform/DesktopStores.kt", ("AppDirs.portable", "FileStore(", "Preferences.userRoot()")),
    "UrlScheme.kt": ("sharedUi/src/desktopMain/kotlin/com/varuna/rustify/ui/UrlScheme.kt", ("if (AppDirs.portable) return", "HKCU")),
}

def api_get(path: str):
    if not path.startswith("/"):
        raise ValueError("Invalid API path")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "rustify-unofficial-portable-builder-b1r1", "X-GitHub-Api-Version": "2022-11-28"}
    if os.getenv("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    url = API + path
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(f"Not found at GitHub API (404): {path}") from exc
        raise RuntimeError(f"GitHub API error HTTP {exc.code} for {path} (401/403/429/5xx are NOT treated as no release)") from exc

def version_key(tag: str):
    m = VERSION.fullmatch(tag)
    if not m:
        return None
    return tuple(map(int, m.groups()[:3]))

def release_sort_key(tag: str):
    """Numeric semver including beta.10 > beta.2; never sort as text."""
    m = VERSION.fullmatch(tag)
    if not m:
        return None
    prerelease_kind = (m.group(4) or '').lower()
    prerelease_rank = {'alpha': 0, 'b': 1, 'beta': 1, 'rc': 2, '': 3}[prerelease_kind]
    prerelease_number = int(m.group(5) or 0)
    return (*version_key(tag), prerelease_rank, prerelease_number)

def release_candidates(channel: str, releases: list[dict]) -> list[dict]:
    selected = []
    for r in releases:
        tag = str(r.get("tag_name", ""))
        v = version_key(tag)
        if not v or r.get("draft"):
            continue
        beta = bool(r.get("prerelease")) or bool(re.search(r"(?:beta|alpha|rc|b)\b|\d+b$", tag, re.I))
        if (channel == "stable" and beta) or (channel == "beta" and not beta):
            continue
        selected.append(r)
    return sorted(selected, key=lambda x: release_sort_key(x["tag_name"]), reverse=True)

def resolve_release(channel: str, explicit_tag: str) -> dict:
    if explicit_tag:
        if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?", explicit_tag):
            raise ValueError("release_tag must be an exact semantic release tag, e.g. v5.6.4-beta")
        r = api_get("/releases/tags/" + urllib.parse.quote(explicit_tag, safe=""))
        if r.get("draft") or version_key(str(r.get("tag_name", ""))) is None:
            raise RuntimeError("Release is draft or version is unsupported")
        beta = bool(r.get("prerelease")) or bool(re.search(r"(beta|alpha|rc)", r["tag_name"], re.I))
        if (channel == "stable" and beta) or (channel == "beta" and not beta):
            raise RuntimeError(f"Selected release {r['tag_name']} does not match channel {channel}. Select the correct channel explicitly.")
        return r
    found = []
    for page in range(1, 11):
        page_releases = api_get(f"/releases?per_page=100&page={page}")
        if not isinstance(page_releases, list):
            raise RuntimeError("Unexpected GitHub release API response")
        found.extend(page_releases)
        if len(page_releases) < 100:
            break
    else:
        raise RuntimeError("Release pagination exceeds 1000; specify release_tag to avoid ambiguous latest")
    ranked = release_candidates(channel, found)
    if not ranked:
        raise RuntimeError(f"No published {channel} releases found. Rustify currently publishes betas. Explicitly select beta (or specific beta tag) to use them.")
    for r in ranked:
        if any(APP_ASSET.fullmatch(a.get("name", "")) for a in r.get("assets", [])):
            return r
    raise RuntimeError(f"Published {channel} versions exist, but none includes an official Windows x64 portable ZIP")

def resolve_commit(tag: str) -> str:
    obj = api_get("/git/ref/tags/" + urllib.parse.quote(tag, safe=""))["object"]
    for _ in range(6):
        sha = obj.get("sha", "")
        if not re.fullmatch(r"[a-fA-F0-9]{40}", sha):
            raise RuntimeError("Invalid upstream Git commit/tag sha")
        if obj.get("type") == "commit":
            return sha.lower()
        if obj.get("type") != "tag":
            raise RuntimeError("Unexpected upstream git object type")
        obj = api_get("/git/tags/" + sha)["object"]
    raise RuntimeError("Too many annotated tag indirections")

def source_fetch(commit: str, relative: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{relative}"
    req = urllib.request.Request(url, headers={"User-Agent": "RustifyPortableBuilder-b1r1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read(8_000_000)
            if response.read(1):
                raise RuntimeError(f"Source file unexpectedly large: {relative}")
            return body
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Source evidence missing at pinned commit: {relative}: HTTP {exc.code}") from exc

def inspect_sources(commit: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, (relative, needles) in PORTABILITY_SOURCES.items():
        blob = source_fetch(commit, relative)
        source = blob.decode("utf-8-sig")
        for needle in needles:
            if needle not in source:
                raise RuntimeError(f"PORTABILITY CONTRACT CHANGED: {relative} missing {needle!r}; stop rather than silently risk host writes")
        (output / name).write_bytes(blob)
        hashes[relative] = hashlib.sha256(blob).hexdigest()
    for name in ("LICENSE", "desktopApp/build.gradle.kts", "gradle/libs.versions.toml", "core_engine/Cargo.lock", "gradle/wrapper/gradle-wrapper.properties"):
        blob = source_fetch(commit, name)
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        hashes[name] = hashlib.sha256(blob).hexdigest()
    return hashes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=["stable", "beta"], required=True)
    parser.add_argument("--tag", default="")
    parser.add_argument("--output", default="work/resolution.json")
    args = parser.parse_args()
    r = resolve_release(args.channel, args.tag)
    assets = [a for a in r.get("assets", []) if APP_ASSET.fullmatch(a.get("name", ""))]
    if len(assets) != 1:
        raise RuntimeError(f"Expected exactly one official Windows portable asset; found {len(assets)}")
    asset = assets[0]
    digest = str(asset.get("digest") or "")
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise RuntimeError("GitHub asset API has no SHA-256 digest. Refusing unverifiable download. Choose a release with GitHub-published digest.")
    url = asset.get("browser_download_url") or ""
    if not url.startswith(f"https://github.com/{REPO}/releases/download/{urllib.parse.quote(r['tag_name'], safe='')}/"):
        raise RuntimeError("Unexpected release asset host/path")
    commit = resolve_commit(r["tag_name"])
    hashes = inspect_sources(commit, Path("work/source-evidence"))
    record = {
        "repository": REPO,
        "channel": args.channel,
        "tag": r["tag_name"],
        "commit": commit,
        "release_id": r["id"],
        "published_at": r.get("published_at"),
        "version": ".".join(map(str, version_key(r["tag_name"]))),
        "prerelease": bool(r.get("prerelease")),
        "asset": {"name": asset["name"], "url": url, "sha256": digest[7:].lower(), "size": asset.get("size"), "asset_id": asset["id"]},
        "source_file_sha256": hashes,
        "builder_revision": "b1r1",
        "package_revision": "r1",
        "builder_commit": os.environ.get("GITHUB_SHA", "local-uncommitted"),
        "shared_package_builder": "vhick/Portable-Package-Builder@v1.0.0",
        "shared_release_publisher": "vhick/portable-release-publisher@v1.1.1",
    }
    identity = f"portable-rustify-{record['tag']}-b1r1-{commit[:8]}-{record['asset']['sha256'][:8]}-{record['builder_commit'][:8]}"
    if len(identity) > 151:
        raise RuntimeError('Generated publisher tag is too long')
    record['candidate_release_tag'] = identity
    p = Path(args.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Resolved:", record["tag"], "upstream commit", commit, "asset digest", record["asset"]["sha256"])
    print("Source checks complete; offline ZIP stage may proceed.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
