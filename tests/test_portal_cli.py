import pathlib
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class PortalRelease(unittest.TestCase):
    def test_first_release_contains_only_initial_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            out = pathlib.Path(temp) / 'released'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--edition', 'original', '--step', '1', '--output', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([p.name for p in out.iterdir()], ['request.txt'])
            text = (out / 'request.txt').read_text()
            self.assertIn('/api/documents', text)
            self.assertNotIn('/api/shares', text)
            self.assertNotIn('/api/search', text)

    def test_later_release_keeps_prior_requests_without_future_search(self):
        with tempfile.TemporaryDirectory() as temp:
            out = pathlib.Path(temp) / 'released'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'release', '--edition', 'original', '--step', '2', '--output', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (out / 'request.txt').read_text()
            self.assertIn('/api/documents', text)
            self.assertIn('/api/shares', text)
            self.assertNotIn('/api/search', text)

    def test_bind_rejects_missing_private_bundle_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            out = pathlib.Path(temp) / 'bound'
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'bind', '--edition', 'original', '--bundle', temp, '--output', str(out)], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('bundle.json', result.stderr)
            self.assertFalse(out.exists())

    def test_pending_checker_qualification_cannot_evaluate_with_prior_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / 'principiis').mkdir()
            (root / 'principiis/__init__.py').touch()
            shutil.copyfile(ROOT / 'principiis/portal.py', root / 'principiis/portal.py')
            package = root / 'benchmarks/document-portal'
            package.mkdir(parents=True)
            bundle = root / 'private'
            bundle.mkdir()
            raw = json.dumps(dict(files={}, qualification_status='pending', evaluator_images={})).encode()
            (bundle / 'bundle.json').write_bytes(raw)
            (package / 'package.json').write_text(json.dumps(dict(private_bundle_sha256=hashlib.sha256(raw).hexdigest())))
            result = subprocess.run([sys.executable, '-m', 'principiis.portal', 'evaluate', '--edition', 'original', '--bundle', str(bundle), '--step', '1', '--snapshot', str(root / 'absent')], cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('checker qualification pending', result.stderr)
            self.assertFalse((bundle / 'runtime').exists())

    def test_author_fixture_variants_reach_restricted_evaluator_preflight(self):
        for variant in ['alternative-layout-slow', 'stale-revocation']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                root = pathlib.Path(temp)
                contract = root / 'contract.json'
                contract.write_text(json.dumps({'browser': 'functional', 'backend': 'security'}))
                output = root / 'assessment'
                image = 'sha256:' + 'a' * 64
                result = subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(ROOT / 'fixtures/evaluation'), '--output', str(output), '--app-image', image, '--evaluator-image', image, '--docker', '/nonexistent/portal-test-docker', '--check-contract', str(contract), '--fixture-variant', variant], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads((output / 'assessment.json').read_text())
                self.assertEqual(record['fixture_variant'], variant)
                self.assertEqual(record['commands'][0], ['/nonexistent/portal-test-docker', 'image', 'inspect', image])
                self.assertEqual(record['outcome'], 'evaluator_error')
                self.assertEqual(record['security'], 'unassessable')
                self.assertEqual(record['exit_statuses'][0], 'launch_error')

    def test_fixture_variant_requires_valid_author_contract_and_unambiguous_mode(self):
        for flags in [[], ['--check-contract', 'contract', '--control', 'alternative'], ['--check-contract', 'contract', '--fixture-variant', '../outside']]:
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as temp:
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
