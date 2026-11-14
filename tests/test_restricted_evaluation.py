import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class RestrictedEvaluation(unittest.TestCase):
    def test_missing_prepared_image_retains_unassessable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / 'assessment'
            result = subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(ROOT / 'fixtures/evaluation'), '--output', str(output), '--app-image', 'missing', '--evaluator-image', 'missing', '--docker', '/nonexistent/docker'], cwd=ROOT, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads((output / 'assessment.json').read_text())
            self.assertEqual(evidence['outcome'], 'evaluator_error')
            self.assertEqual(evidence['security'], 'unassessable')
            self.assertTrue(evidence['snapshot_sha256'])

    def test_invalid_snapshot_is_retained_as_unassessable(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / 'assessment'
            result = subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', directory + '/absent', '--output', str(output), '--app-image', 'missing', '--evaluator-image', 'missing'], cwd=ROOT, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads((output / 'assessment.json').read_text())
            self.assertEqual(evidence['outcome'], 'evaluator_error')
            self.assertIsNone(evidence['snapshot_sha256'])
