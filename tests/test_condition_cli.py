"""Exercise the real operator initialization path without starting a model."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ConditionCLI(unittest.TestCase):
    def test_root_help_shows_operator_commands(self):
        result = subprocess.run([sys.executable, '-m', 'principiis', '--help'], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('develop', result.stdout)
        self.assertIn('compare', result.stdout)
        self.assertIn('evaluate', result.stdout)
        self.assertNotIn('assess-final', result.stdout)
        self.assertNotIn('bind-evaluator', result.stdout)

    def test_removed_legacy_run_commands_are_rejected(self):
        for command in ('run', 'sequence'):
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, str(ROOT / 'bin/principiis'), command, '--help'],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('invalid choice', result.stderr)

    def test_init_freezes_baseline_condition_and_investigation_choice(self):
        with temporary_directory() as directory:
            base = Path(directory)
            auth = base / 'auth.json'
            auth.write_text('separately provisioned test file')
            runtime = base / 'runtime.json'
            runtime.write_text(json.dumps({
                'version': '1', 'docker': '/usr/bin/true',
                'image': 'sha256:' + 'a' * 64, 'auth_file': str(auth),
                'clean_runtime_review': 'test initialization only',
            }))
            command = [sys.executable, '-m', 'principiis', 'init', '--run', 'first',
                       '--runs-root', str(base / 'runs'), '--application', 'document-portal',
                       '--runtime-config', str(runtime), '--condition', 'baseline',
                       '--investigation', 'final']
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            root = base / 'runs/first'
            sequence = json.loads((root / 'sequence.json').read_text())
            self.assertEqual(sequence['condition']['id'], 'baseline')
            self.assertEqual(sequence['condition']['version'], '1')
            self.assertEqual(json.loads((root / 'condition.json').read_text())['kind'], 'ordinary')
            self.assertEqual(json.loads((root / 'configuration.json').read_text())['investigation'], 'final')
            self.assertIn('condition.json', json.loads((root / 'configuration.json').read_text())['frozen_files'])
            (root / 'condition.json').write_text('{}')
            status = subprocess.run([sys.executable, '-m', 'principiis', 'status', '--run', 'first',
                                     '--runs-root', str(base / 'runs')], cwd=ROOT,
                                    capture_output=True, text=True)
            self.assertNotEqual(status.returncode, 0)
            self.assertIn('saved development configuration changed', status.stderr)

    def test_init_binds_available_qualified_evaluator_and_rejects_bad_manifest(self):
        manifest = ROOT / 'private/benchmarks/document-portal-v3/release-manifest.json'
        package = json.loads((ROOT / 'benchmarks/document-portal/package.json').read_text())
        if not manifest.is_file() or hashlib.sha256(manifest.read_bytes()).hexdigest() != package.get('private_bundle_sha256'):
            self.skipTest('qualified local evaluator release is unavailable')
        with temporary_directory() as directory:
            base = Path(directory)
            auth = base / 'auth.json'
            auth.write_text('configuration check only; no live model')
            runtime = base / 'runtime.json'
            runtime.write_text(json.dumps({
                'version': '1', 'docker': '/usr/bin/true',
                'image': json.loads(manifest.read_text())['runtime_image'],
                'auth_file': str(auth), 'clean_runtime_review': 'configuration check only',
            }))
            prefix = [sys.executable, '-m', 'principiis', 'init', '--application', 'document-portal',
                      '--runs-root', str(base / 'runs'), '--runtime-config', str(runtime)]
            bad = subprocess.run(prefix + ['--run', 'bad', '--evaluator-manifest', str(base / 'missing.json')],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertFalse((base / 'runs/bad').exists())
            good = subprocess.run(prefix + ['--run', 'good', '--evaluator-manifest', str(manifest),
                                            '--format', 'json'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            status = json.loads(good.stdout)
            self.assertIsNotNone(status['assessment_binding'])
            self.assertEqual(status['next_action']['action'], 'develop')
            self.assertFalse((base / 'runs/good/development').exists())

    def test_final_review_selects_last_checkpoint_and_requires_primary(self):
        with temporary_directory() as directory:
            base = Path(directory)
            auth = base / 'auth.json'
            auth.write_text('test')
            runtime = base / 'runtime.json'
            runtime.write_text(json.dumps({
                'version': '1', 'docker': '/usr/bin/true',
                'image': 'sha256:' + 'a' * 64, 'auth_file': str(auth),
                'clean_runtime_review': 'test initialization only',
            }))
            prefix = [sys.executable, '-m', 'principiis']
            common = ['--run', 'first', '--runs-root', str(base / 'runs')]
            started = subprocess.run(prefix + ['init', *common, '--application', 'document-portal',
                                              '--runtime-config', str(runtime)], cwd=ROOT,
                                     capture_output=True, text=True)
            self.assertEqual(started.returncode, 0, started.stderr)
            result = subprocess.run(prefix + ['evaluate', *common, '--final', '--ai-review', '--config', 'unused',
                                              '--prompt', 'unused', '--prompt-version', '1'], cwd=ROOT,
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('completed checkpoint and primary assessment required', result.stderr)
            self.assertFalse((base / 'runs/first/investigations').exists())
            logs = subprocess.run(prefix + ['logs', *common, '--format', 'json'], cwd=ROOT,
                                  capture_output=True, text=True)
            self.assertEqual(logs.returncode, 0, logs.stderr)
            events = [json.loads(line) for line in logs.stdout.splitlines()]
            self.assertEqual([event['event'] for event in events], ['started', 'failed'])
            self.assertEqual([event['step'] for event in events], ['step-03', 'step-03'])

    def test_final_step_selects_three_and_ten_step_sequences(self):
        from principiis.operator import final_step
        with temporary_directory() as directory:
            root = Path(directory)
            for count in (3, 10):
                (root / 'sequence.json').write_text(json.dumps({
                    'steps': [{'id': f'step-{number:02}'} for number in range(1, count + 1)]
                }))
                self.assertEqual(final_step(root), f'step-{count:02}')

    def test_evaluate_review_flags_select_review_without_starting_it(self):
        command = [sys.executable, '-m', 'principiis', 'evaluate', '--run', 'unused',
                   '--step', '1']
        missing = subprocess.run(command + ['--ai-review'], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('--ai-review requires --config', missing.stderr)
        misplaced = subprocess.run(command + ['--prompt', '/unused'], cwd=ROOT,
                                   capture_output=True, text=True)
        self.assertNotEqual(misplaced.returncode, 0)
        self.assertIn('reviewer options require --ai-review', misplaced.stderr)

    def test_status_shows_incomplete_investigation_allocation(self):
        with temporary_directory() as directory:
            base = Path(directory)
            auth = base / 'auth.json'
            auth.write_text('test')
            runtime = base / 'runtime.json'
            runtime.write_text(json.dumps({
                'version': '1', 'docker': '/usr/bin/true',
                'image': 'sha256:' + 'a' * 64, 'auth_file': str(auth),
                'clean_runtime_review': 'test initialization only',
            }))
            prefix = [sys.executable, '-m', 'principiis']
            common = ['--run', 'first', '--runs-root', str(base / 'runs')]
            started = subprocess.run(prefix + ['init', *common, '--application', 'document-portal',
                                              '--runtime-config', str(runtime)], cwd=ROOT,
                                     capture_output=True, text=True)
            self.assertEqual(started.returncode, 0, started.stderr)
            (base / 'runs/first/investigations/step-01/1').mkdir(parents=True)
            status = subprocess.run(prefix + ['status', *common, '--format', 'json'], cwd=ROOT,
                                    capture_output=True, text=True)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)['investigations'][0]['status'], 'interrupted_allocation')

    def test_unimplemented_condition_does_not_allocate_run(self):
        with temporary_directory() as directory:
            base = Path(directory)
            auth = base / 'auth.json'
            auth.write_text('test')
            runtime = base / 'runtime.json'
            runtime.write_text(json.dumps({
                'version': '1', 'docker': '/usr/bin/true',
                'image': 'sha256:' + 'a' * 64, 'auth_file': str(auth),
                'clean_runtime_review': 'test initialization only',
            }))
            result = subprocess.run([
                sys.executable, '-m', 'principiis', 'init', '--run', 'first',
                '--runs-root', str(base / 'runs'), '--application', 'document-portal',
                '--runtime-config', str(runtime), '--condition', 'unknown',
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((base / 'runs/first').exists())

    def test_draft_application_cannot_allocate_scored_run(self):
        with temporary_directory() as directory:
            base = Path(directory)
            auth = base / 'auth.json'
            auth.write_text('test')
            runtime = base / 'runtime.json'
            runtime.write_text(json.dumps({
                'version': '1', 'docker': '/usr/bin/true',
                'image': 'sha256:' + 'a' * 64, 'auth_file': str(auth),
                'clean_runtime_review': 'test initialization only',
            }))
            result = subprocess.run([
                sys.executable, '-m', 'principiis', 'init', '--run', 'first',
                '--runs-root', str(base / 'runs'), '--application', 'customer-support-desk',
                '--runtime-config', str(runtime), '--steps', '10',
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('qualified', result.stderr)
            self.assertFalse((base / 'runs/first').exists())


if __name__ == '__main__':
    unittest.main()
