"""Approved seam: cumulative release artifacts, never application internals."""
import hashlib
import json
import shutil
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class FullPortalRelease(unittest.TestCase):
    def test_tenth_release_contains_exactly_ten_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / 'release'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--edition', 'full-v1', '--step', '10', '--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([p.name for p in output.iterdir()], ['request.txt'])
            text = (output / 'request.txt').read_text()
            self.assertEqual(text.count('Request '), 10)
            self.assertIn('/api/collections/{id}/transfer', text)

    def test_fourth_release_preserves_original_requests_without_sharing_future(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / 'release'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--edition', 'full-v1', '--step', '4', '--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (output / 'request.txt').read_text()
            self.assertIn('/api/imports', text)
            self.assertIn('/api/exports', text)
            self.assertNotIn('/api/shares', text)
            self.assertNotIn('/revisions', text)
            self.assertEqual(text.count('Request '), 4)

    def test_legacy_edition_rejects_future_step_without_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / 'release'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--edition', 'real-v1', '--step', '4', '--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_controller_binds_ten_steps_and_pending_evaluation_never_stages(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / 'principiis').mkdir()
            (root / 'principiis/__init__.py').touch()
            shutil.copyfile(ROOT / 'principiis/portal.py', root / 'principiis/portal.py')
            package = root / 'benchmarks/document-portal-full'
            shutil.copytree(ROOT / 'benchmarks/document-portal-full', package)
            bundle = root / 'private'
            bundle.mkdir()
            raw = json.dumps({'files': {}, 'qualification_status': 'pending'}).encode()
            (bundle / 'bundle.json').write_bytes(raw)
            metadata = json.loads((package / 'package.json').read_text())
            metadata['private_bundle_sha256'] = hashlib.sha256(raw).hexdigest()
            (package / 'package.json').write_text(json.dumps(metadata))
            output = root / 'controller'
            command = [sys.executable, '-m', 'principiis.portal']
            result = subprocess.run(command + ['bind', '--edition', 'full-v1', '--bundle', str(bundle), '--output', str(output)], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output / 'sequence.json').read_text())
            self.assertEqual([s['id'] for s in manifest['steps']], ['portal-'+str(i) for i in range(1,11)])
            self.assertEqual(manifest['steps'][-1]['request'], '10.txt')
            result = subprocess.run(command + ['evaluate', '--edition', 'full-v1', '--step', '10', '--bundle', str(bundle), '--snapshot', str(root / 'missing-candidate')], cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('checker qualification pending', result.stderr)
            self.assertFalse((bundle / 'runtime').exists())
