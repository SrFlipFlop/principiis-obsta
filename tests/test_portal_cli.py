import pathlib
import json
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class PortalRelease(unittest.TestCase):
    def test_removed_synthetic_edition_is_not_releasable(self):
        with temporary_directory() as temp:
            out = pathlib.Path(temp) / 'released'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--edition', 'original', '--step', '1', '--output', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_first_release_contains_only_initial_contract(self):
        with temporary_directory() as temp:
            out = pathlib.Path(temp) / 'released'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--step', '1', '--output', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([p.name for p in out.iterdir()], ['request.txt'])
            text = (out / 'request.txt').read_text()
            self.assertIn('/api/documents', text)
            self.assertNotIn('/api/shares', text)
            self.assertNotIn('/api/search', text)

    def test_later_release_keeps_prior_requests_without_future_search(self):
        with temporary_directory() as temp:
            out = pathlib.Path(temp) / 'released'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--step', '2', '--output', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (out / 'request.txt').read_text()
            self.assertIn('/api/documents', text)
            self.assertIn('/api/collections', text)
            self.assertNotIn('/api/search', text)

    def test_author_fixture_variants_reach_restricted_evaluator_preflight(self):
        for variant in ['alternative-layout-slow', 'stale-revocation']:
            with self.subTest(variant=variant), temporary_directory() as temp:
                root = pathlib.Path(temp)
                contract = root / 'contract.json'
                contract.write_text(json.dumps({'browser': 'functional', 'backend': 'security'}))
                output = root / 'assessment'
                image = 'sha256:' + 'a' * 64
                result = subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(ROOT / 'fixtures/evaluation'), '--output', str(output), '--app-image', image, '--evaluator-image', image, '--docker', '/nonexistent/portal-test-docker', '--check-contract', str(contract), '--fixture-variant', variant], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads((output / 'assessment.json').read_text())
                self.assertEqual(record['fixture_variant'], variant)
                self.assertEqual(record['commands'][0], ['/nonexistent/portal-test-docker', '--host',
                    'unix:///var/run/docker.sock', 'image', 'inspect', image])
                self.assertEqual(record['outcome'], 'evaluator_error')
                self.assertEqual(record['security'], 'unassessable')
                self.assertEqual(record['exit_statuses'][0], 'launch_error')

    def test_fixture_variant_requires_valid_author_contract_and_unambiguous_mode(self):
        for flags in [[], ['--check-contract', 'contract', '--control', 'alternative'], ['--check-contract', 'contract', '--fixture-variant', '../outside']]:
            with self.subTest(flags=flags), temporary_directory() as temp:
                root = pathlib.Path(temp)
                contract = root / 'contract.json'
                contract.write_text(json.dumps({'browser': 'functional', 'backend': 'security'}))
                options = [str(contract) if value == 'contract' else value for value in flags]
                output = root / 'assessment'
                image = 'sha256:' + 'a' * 64
                result = subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(ROOT / 'fixtures/evaluation'), '--output', str(output), '--app-image', image, '--evaluator-image', image, '--docker', '/nonexistent/portal-test-docker', '--fixture-variant', 'alternative-layout-slow', *options], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads((output / 'assessment.json').read_text())
                self.assertIn('fixture variant requires', record['error'])
                self.assertFalse(any(command[1:3] == ['image', 'inspect'] for command in record['commands']))
                self.assertEqual(record['outcome'], 'evaluator_error')
