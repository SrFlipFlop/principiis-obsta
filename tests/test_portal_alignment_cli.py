"""Exercise the approved public authoring boundary through release artifacts."""
import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AlignedPortalRelease(unittest.TestCase):
    def test_one_package_default_releases_tenth_step(self):
        with temporary_directory() as temp:
            out = Path(temp) / 'released'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release',
                                     '--step', '10', '--output', str(out)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (out / 'request.txt').read_text()
            self.assertEqual(text.count('Request '), 10)
            self.assertTrue((ROOT / 'benchmarks/document-portal').is_dir())
            for deprecated in ['document-portal-real', 'document-portal-full']:
                self.assertFalse((ROOT / 'benchmarks' / deprecated).exists())

    def test_short_request_retains_product_roles_without_security_instructions(self):
        with temporary_directory() as temp:
            out = Path(temp) / 'released'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release',
                                     '--step', '2', '--output', str(out)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (out / 'request.txt').read_text()
            self.assertIn('reader', text.lower())
            self.assertIn('editor', text.lower())
            self.assertNotIn('bundled dependencies and the Python standard library only', text)
            self.assertNotIn('including links they already have', text)
            self.assertNotIn('Passwords are at least eight characters', text)
            self.assertNotIn('get_by_label', text)
            self.assertNotIn('/api/search', text)
            self.assertIn('requirements.txt', text)
            metadata = json.loads((ROOT / 'benchmarks/document-portal/package.json').read_text())
            self.assertEqual(metadata['version'], 'v3-draft1')
            self.assertEqual(metadata['qualification_status'], 'qualified_first_three')
            self.assertEqual(metadata['owner_review'], 'approved_first_three')
            self.assertEqual(metadata['qualified_through'], 3)
            self.assertRegex(metadata['private_bundle_sha256'], r'^[0-9a-f]{64}$')
