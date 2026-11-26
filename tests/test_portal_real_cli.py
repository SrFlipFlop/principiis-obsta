"""Approved seam: released CLI artifacts; no candidate execution on the host."""
import json
import shutil
import pathlib
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class RealPortalRelease(unittest.TestCase):
    def test_initial_release_is_usable_portal_without_later_requests(self):
        with temporary_directory() as temp:
            out = pathlib.Path(temp) / 'released'
            r = subprocess.run([sys.executable, '-m', 'principiis.benchmark', 'release', '--application', 'document-portal', '--step', '1', '--output', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual([p.name for p in out.iterdir()], ['request.txt'])
            request = (out / 'request.txt').read_text()
            for phrase in ['password', 'sqlite', 'upload', '/api/documents', 'download']:
                self.assertIn(phrase, request.lower())
            self.assertNotIn('/api/collections', request)
            self.assertNotIn('/api/search', request)
            self.assertNotIn('X-User', request)

    def test_second_release_retains_build_without_future_archive_change(self):
        with temporary_directory() as temp:
            out = pathlib.Path(temp) / 'released'
            r = subprocess.run([sys.executable, '-m', 'principiis.benchmark', 'release', '--application', 'document-portal', '--step', '2', '--output', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            request = (out / 'request.txt').read_text()
            self.assertIn('/api/session', request)
            self.assertIn('/api/collections', request)
            self.assertNotIn('/api/search', request)
            self.assertNotIn('Restore', request)

    def test_modified_frozen_request_is_rejected_before_release(self):
        with temporary_directory() as temp:
            root = pathlib.Path(temp)
            (root/'principiis').mkdir()
            (root/'principiis/__init__.py').touch()
            shutil.copyfile(ROOT/'principiis/benchmark.py',root/'principiis/benchmark.py')
            package=root/'benchmarks/document-portal'
            shutil.copytree(ROOT/'benchmarks/document-portal',package)
            with (package/'requests/01.txt').open('a') as f:f.write('Unexpected changed requirement')
            out=root/'released'
            r=subprocess.run([sys.executable,'-m','principiis.benchmark','release','--application','document-portal','--step','1','--output',str(out)],cwd=root,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('package content mismatch',r.stderr)
            self.assertFalse(out.exists())
