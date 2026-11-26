"""Benchmark applications are data packages: a directory plus a private evaluator declaration."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:' + 'a' * 64
CHECKER = 'sha256:' + 'b' * 64


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class BenchmarkPackageCLI(unittest.TestCase):
    """Operator `init` and authoring `release` against a copied controller with its own benchmarks."""

    def setUp(self):
        self.directory = temporary_directory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.source = self.base / 'controller'
        shutil.copytree(ROOT / 'principiis', self.source / 'principiis',
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.benchmarks = self.source / 'benchmarks'
        shutil.copytree(ROOT / 'benchmarks/document-portal', self.benchmarks / 'document-portal')
        self.runs = self.base / 'runs'
        (self.base / 'auth.json').write_text('unused engineering fixture credential')
        self.runtime = self.base / 'runtime.json'
        self.runtime.write_text(json.dumps({
            'version': '1', 'docker': '/usr/bin/true', 'image': IMAGE,
            'auth_file': str(self.base / 'auth.json'),
            'clean_runtime_review': 'engineering fixture, not a runtime qualification',
        }))

    def fixture_app(self, name='fixture-ledger', steps=2, qualified_through=2):
        """Author a new application purely as data, with its private evaluator declaration."""
        package = self.benchmarks / name
        (package / 'requests').mkdir(parents=True)
        (package / 'README.md').write_text('Fixture ledger benchmark.\n')
        for number in range(1, steps + 1):
            (package / f'requests/{number:02}.txt').write_text(f'Request {number}: ledger feature {number}.\n')
        private = self.base / 'private' / name
        private.mkdir(parents=True)
        (private / 'contract.json').write_text(json.dumps({'ledger-read': 'functional', 'ledger-isolation': 'security'}))
        (private / 'seccomp.json').write_text('{}')
        (private / 'preparation.json').write_text('{"kind":"fixture preparation receipt"}')
        (private / 'dependencies.json').write_text(json.dumps({'complete': True, 'images': {
            image: {'packages': [{'name': 'python', 'version': '3.12'}], 'preparation_evidence': ['preparation.json']}
            for image in (IMAGE, CHECKER)}}))
        ids = [f'step-{number:02}' for number in range(1, qualified_through + 1)]
        declaration = {
            'version': 'fixture-ledger-evaluator-1', 'complete': True,
            'requests': {f'requests/{number:02}.txt': digest(package / f'requests/{number:02}.txt')
                         for number in range(1, qualified_through + 1)},
            'runtime_image': IMAGE, 'evaluator_images': {step: CHECKER for step in ids},
            'evaluator_command': ['python3', '/checks/run.py'],
            'seccomp': 'seccomp.json', 'dependency_manifest': 'dependencies.json',
            'steps': {step: {'contract': 'contract.json', 'app_command': ['python', 'app.py']} for step in ids},
            'files': {path.name: digest(path) for path in private.iterdir()},
        }
        manifest = private / 'release-manifest.json'
        manifest.write_text(json.dumps(declaration))
        (package / 'package.json').write_text(json.dumps({
            'id': name, 'version': 'fixture-v1', 'steps': steps, 'qualified_through': qualified_through,
            'private_bundle_sha256': digest(manifest),
            'files': {str(path.relative_to(package)): digest(path)
                      for path in sorted(package.rglob('*')) if path.is_file()},
        }))
        return package, manifest

    def principiis(self, *arguments, success=True):
        completed = subprocess.run([sys.executable, '-m', 'principiis', *arguments],
                                   cwd=self.source, capture_output=True, text=True)
        if success:
            self.assertEqual(completed.returncode, 0, completed.stderr)
        else:
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
        return completed

    def init(self, application, run, *arguments, success=True):
        return self.principiis('init', '--application', application, '--run', run,
                               '--runs-root', str(self.runs), '--runtime-config', str(self.runtime),
                               '--format', 'json', *arguments, success=success)

    def test_new_application_needs_only_its_directory_and_private_declaration(self):
        package, manifest = self.fixture_app()
        status = json.loads(self.init('fixture-ledger', 'ledger', '--steps', '2',
                                      '--evaluator-manifest', str(manifest)).stdout)
        self.assertEqual(status['assessment_binding']['manifest_sha256'], digest(manifest))
        self.assertEqual(status['next_action']['action'], 'develop')
        run = self.runs / 'ledger'
        self.assertEqual([checkpoint['id'] for checkpoint in status['checkpoints']], ['step-01', 'step-02'])
        self.assertEqual((run / 'requests/02.txt').read_bytes(), (package / 'requests/02.txt').read_bytes())

    def test_step_count_is_bounded_by_the_qualified_evaluator(self):
        self.fixture_app(steps=12, qualified_through=11)
        rejected = self.init('fixture-ledger', 'too-long', '--steps', '12', success=False)
        self.assertIn('qualified through step 11', rejected.stderr)
        self.assertFalse((self.runs / 'too-long').exists())
        self.init('fixture-ledger', 'eleven', '--steps', '11')
        status = self.principiis('status', '--run', 'eleven', '--runs-root', str(self.runs))
        self.assertIn('| step-11 | not-started |', status.stdout)
        self.assertIn('--step 1', status.stdout)
        logs = self.principiis('logs', '--run', 'eleven', '--runs-root', str(self.runs), '--step', '11')
        self.assertEqual(logs.returncode, 0)

    def test_unqualified_application_cannot_start_a_run(self):
        self.fixture_app(qualified_through=0)
        rejected = self.init('fixture-ledger', 'unqualified', success=False)
        self.assertIn('qualified through step 0', rejected.stderr)

    def test_portal_ten_step_run_is_rejected_until_its_evaluator_is_qualified(self):
        rejected = self.init('document-portal', 'ten-steps', '--steps', '10', success=False)
        self.assertIn('qualified through step 3', rejected.stderr)
        self.assertFalse((self.runs / 'ten-steps').exists())

    def test_full_sequence_requires_the_private_evaluator_at_init(self):
        self.fixture_app()
        rejected = self.init('fixture-ledger', 'unbound', '--steps', '2', success=False)
        self.assertIn('--evaluator-manifest', rejected.stderr)

    def test_released_request_must_match_package_bytes(self):
        package, _ = self.fixture_app()
        with (package / 'requests/01.txt').open('a') as stream:
            stream.write('Unexpected changed requirement\n')
        rejected = self.init('fixture-ledger', 'changed', '--steps', '1', success=False)
        self.assertIn('content mismatch', rejected.stderr)

    def test_empty_request_is_not_a_frozen_package(self):
        package, _ = self.fixture_app()
        (package / 'requests/02.txt').write_text(' \n')
        metadata = json.loads((package / 'package.json').read_text())
        metadata['files']['requests/02.txt'] = digest(package / 'requests/02.txt')
        (package / 'package.json').write_text(json.dumps(metadata))
        rejected = self.init('fixture-ledger', 'empty', '--steps', '1', success=False)
        self.assertIn('nonempty', rejected.stderr)

    def test_request_reached_through_a_symlink_is_not_a_frozen_package(self):
        package, _ = self.fixture_app()
        request = package / 'requests/02.txt'
        outside = self.base / 'outside-request.txt'
        outside.write_bytes(request.read_bytes())
        request.unlink()
        request.symlink_to(outside)
        rejected = self.init('fixture-ledger', 'linked', '--steps', '1', success=False)
        self.assertIn('regular files', rejected.stderr)

    def test_release_publishes_cumulative_requests_for_any_application(self):
        self.fixture_app(steps=3, qualified_through=1)
        output = self.base / 'released'
        released = subprocess.run([sys.executable, '-m', 'principiis.benchmark', 'release',
                                   '--application', 'fixture-ledger', '--step', '2', '--output', str(output)],
                                  cwd=self.source, capture_output=True, text=True)
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertEqual([path.name for path in output.iterdir()], ['request.txt'])
        text = (output / 'request.txt').read_text()
        self.assertIn('ledger feature 2', text)
        self.assertNotIn('ledger feature 3', text)
        beyond = subprocess.run([sys.executable, '-m', 'principiis.benchmark', 'release',
                                 '--application', 'fixture-ledger', '--step', '4',
                                 '--output', str(self.base / 'beyond')],
                                cwd=self.source, capture_output=True, text=True)
        self.assertNotEqual(beyond.returncode, 0)
        self.assertFalse((self.base / 'beyond').exists())


class RepositoryPackages(unittest.TestCase):
    def test_every_benchmark_declares_qualified_through_instead_of_owner_review(self):
        packages = sorted(path for path in (ROOT / 'benchmarks').iterdir() if (path / 'package.json').is_file())
        self.assertEqual(len(packages), 5)
        for package in packages:
            metadata = json.loads((package / 'package.json').read_text())
            with self.subTest(application=package.name):
                self.assertNotIn('owner_review', metadata)
                self.assertNotIn('qualification_status', metadata)
                self.assertIs(type(metadata['qualified_through']), int)
                for name, expected in metadata['files'].items():
                    self.assertEqual(digest(package / name), expected, name)

    def test_portal_keeps_its_three_step_evaluator_binding(self):
        metadata = json.loads((ROOT / 'benchmarks/document-portal/package.json').read_text())
        self.assertEqual(metadata['qualified_through'], 3)
        # The private evaluator declaration digest and the frozen request bytes it pins are unchanged.
        self.assertEqual(metadata['private_bundle_sha256'],
                         '59d3ed41f702b5c2557571202c95f17e4b6d0955d74b9d66eadfb7b5c9c0425c')
        self.assertEqual({name: metadata['files'][name] for name in ('requests/01.txt', 'requests/02.txt', 'requests/03.txt')}, {
            'requests/01.txt': '426fefe2bdb558eb3c9fe558faa8b9e8f33dc8489c9c275f5b1d96aaa4ed93fe',
            'requests/02.txt': 'be6615ca34246d0d32b66530532f1284a13cb072e80f58e9871539cc6a514bd9',
            'requests/03.txt': 'e39ec895c09d0f412d7d6a83dd0e1837c5c34caef9d997802e30917df29b2ad5',
        })


if __name__ == '__main__':
    unittest.main()
