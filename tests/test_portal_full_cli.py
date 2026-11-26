"""Approved seam: cumulative release artifacts, never application internals."""
import pathlib
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class FullPortalRelease(unittest.TestCase):
    def test_tenth_release_contains_exactly_ten_requests(self):
        with temporary_directory() as temp:
            output = pathlib.Path(temp) / 'release'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--step', '10', '--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([p.name for p in output.iterdir()], ['request.txt'])
            text = (output / 'request.txt').read_text()
            self.assertEqual(text.count('Request '), 10)
            self.assertIn('/api/collections/{id}/transfer', text)

    def test_fourth_release_preserves_original_requests_without_sharing_future(self):
        with temporary_directory() as temp:
            output = pathlib.Path(temp) / 'release'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--step', '4', '--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (output / 'request.txt').read_text()
            self.assertIn('/api/imports', text)
            self.assertIn('/api/exports', text)
            self.assertNotIn('/api/shares', text)
            self.assertNotIn('/revisions', text)
            self.assertEqual(text.count('Request '), 4)

    def test_out_of_range_step_does_not_create_output(self):
        with temporary_directory() as temp:
            output = pathlib.Path(temp) / 'release'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--step', '11', '--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
