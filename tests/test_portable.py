import hashlib
import json
from unittest.mock import patch
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts import resolve, stage

class ReleaseTests(unittest.TestCase):
    def test_numeric_semver(self):
        tags = ['v5.9.1-beta', 'v5.10.0-beta', 'v4.8.2-beta']
        self.assertEqual(max(tags, key=resolve.version_key), 'v5.10.0-beta')
    def test_numeric_prerelease_sort(self):
        src = [{'tag_name':tag, 'draft':False, 'prerelease':True} for tag in ('v5.6.4-beta.2','v5.6.4-beta.10','v5.6.4-rc.1')]
        self.assertEqual([x['tag_name'] for x in resolve.release_candidates('beta',src)],
                         ['v5.6.4-rc.1','v5.6.4-beta.10','v5.6.4-beta.2'])
    def test_no_beta_when_stable(self):
        src = [{'tag_name':'v5.6.4-beta','draft':False,'prerelease':True},
               {'tag_name':'v4.8.2','draft':False,'prerelease':False}]
        self.assertEqual([x['tag_name'] for x in resolve.release_candidates('stable',src)], ['v4.8.2'])
        self.assertEqual([x['tag_name'] for x in resolve.release_candidates('beta',src)], ['v5.6.4-beta'])
    def test_nonsemver_is_ignored(self):
        self.assertIsNone(resolve.version_key('latest'))
        self.assertIsNone(resolve.version_key('v5.4.0-beta-untrusted-extra-not-supported'))

class ArchiveTests(unittest.TestCase):
    def test_reject_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/'in.zip'
            with zipfile.ZipFile(z,'w') as f:
                f.writestr('Rustify/../../unrelated.txt',b'bad')
            with self.assertRaises(ValueError): stage.safe_unzip(z,Path(tmp)/'unpacked')
    def test_reject_unrelated_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/'in.zip'
            with zipfile.ZipFile(z,'w') as f: f.writestr('OtherApp/fake.exe',b'bad')
            with self.assertRaises(ValueError): stage.safe_unzip(z,Path(tmp)/'unpacked')
    def test_extract_empty_directory_trees(self):
        with tempfile.TemporaryDirectory() as tmp:
            z=Path(tmp)/'in.zip'
            with zipfile.ZipFile(z,'w') as f:
                f.writestr('Rustify/',b'')
                f.writestr('Rustify/data/settings/nested-empty/',b'')
                f.writestr('Rustify/portable',b'')
            target=Path(tmp)/'unpacked'
            stage.safe_unzip(z,target)
            self.assertTrue((target/'Rustify/data/settings/nested-empty').is_dir())
    def test_zip_preserves_completely_empty_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'RustifyPortable'
            (root/'Data/RustifyProfile/cache/empty/nested').mkdir(parents=True)
            f=Path(tmp)/'out.zip'
            stage.zip_package(root,f)
            with zipfile.ZipFile(f) as z:
                self.assertIn('RustifyPortable/Data/RustifyProfile/cache/empty/nested/',z.namelist())
    def test_pe_rejects_text_and_short(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake.exe'; p.write_bytes(b'MZnot-a-real-program')
            self.assertFalse(stage.is_pe(p))

class MetadataTests(unittest.TestCase):
    def test_appinfo(self):
        t=stage.metadata('v5.6.4-beta','5.6.4')
        self.assertIn('AppID=RustifyVhickPortable',t)
        self.assertIn('PackageVersion=5.6.4.0',t)
        self.assertIn('Start=RustifyPortable.exe',t)
    def test_invalid_packageversion(self):
        with self.assertRaises(ValueError): stage.metadata('v90000.0.0-beta','90000.0.0')

if __name__=='__main__': unittest.main()

# Staging-only synthetic integration fixture. These 128-byte PE-like fixtures are
# created in a TemporaryDirectory and NEVER shipped as application or launcher.
class StageIntegrationFixtureTests(unittest.TestCase):
    @staticmethod
    def fixture_pe():
        b=bytearray(256)
        b[:2]=b'MZ'
        b[0x3c:0x40]=(0x80).to_bytes(4,'little')
        b[0x80:0x84]=b'PE\0\0'
        b[0x84:0x86]=(0x8664).to_bytes(2,'little')
        return bytes(b)
    def test_synthetic_stage_to_zip_preserves_empty_trees(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            w=root/'work'; w.mkdir()
            upstream=w/'upstream-portable.zip'
            with zipfile.ZipFile(upstream,'w') as z:
                z.writestr('Rustify/Rustify.exe',self.fixture_pe())
                z.writestr('Rustify/portable',b'')
                z.writestr('Rustify/app/Rustify.cfg',b'fixture configuration')
                z.writestr('Rustify/runtime/bin/a.txt',b'fixture runtime')
                z.writestr('Rustify/app/resources/windows-x64/core_engine.dll',self.fixture_pe())
                z.writestr('Rustify/app/resources/windows-x64/rustify-login.exe',self.fixture_pe())
                z.writestr('Rustify/some-empty-tree/',b'')
            (w/'RustifyPortable.exe').write_bytes(self.fixture_pe())
            src=w/'source-evidence'; src.mkdir()
            (src/'LICENSE').write_text('synthetic license test fixture')
            meta={'repository':'PabloSoage/Rustify','tag':'v5.6.4-beta','version':'5.6.4',
                  'channel':'beta','asset':{'sha256':stage.sha(upstream)},
                  'commit':'a'*40,'builder_commit':'b'*40,'builder_revision':'b1r1'}
            (w/'resolution.json').write_text(json.dumps(meta),encoding='utf-8')
            with patch.object(stage,'WORK',w), patch.object(stage,'PACKAGE',w/'RustifyPortable'), patch.object(stage,'RELEASE',root/'release-out'):
                stage.build()
                archive=next((root/'release-out').glob('*.zip'))
                stage.validate_zip(archive)
                with zipfile.ZipFile(archive) as z:
                    self.assertIn('RustifyPortable/Data/RustifyProfile/cache/',z.namelist())
                    self.assertIn('RustifyPortable/App/Rustify/some-empty-tree/',z.namelist())
                self.assertTrue((w/'stage-result.json').is_file())
