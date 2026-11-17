"""Approved operator/artifact seam: full runs require qualified frozen requests."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QualifiedSequenceCLI(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.source = self.base / 'controller'
        shutil.copytree(ROOT / 'principiis', self.source / 'principiis',
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.package = self.source / 'benchmarks/document-portal'
        shutil.copytree(ROOT / 'benchmarks/document-portal', self.package)
        self.runs = self.base / 'runs'
        (self.base / 'auth.json').write_text('unused engineering fixture credential')
        self.runtime = self.base / 'runtime.json'
        self.runtime.write_text(json.dumps({
            'version': '1', 'docker': '/usr/bin/true', 'image': 'sha256:' + 'a' * 64,
            'auth_file': str(self.base / 'auth.json'),
            'clean_runtime_review': 'engineering fixture, not a runtime qualification',
        }))

    def init(self, success=False):
        completed = subprocess.run([
            sys.executable, '-m', 'principiis', 'init', '--application', 'document-portal',
            '--run', 'ten-steps', '--runs-root', str(self.runs),
            '--runtime-config', str(self.runtime), '--steps', '10',
        ], cwd=self.source, capture_output=True, text=True)
        if success:
            self.assertEqual(completed.returncode, 0, completed.stderr)
        else:
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
            self.assertFalse((self.runs / 'ten-steps').exists())
        return completed

    def qualified_fixture(self):
        metadata = json.loads((self.package / 'package.json').read_text())
        metadata.update(qualification_status='qualified', owner_review='approved',
                        private_bundle_sha256='b' * 64)
        (self.package / 'package.json').write_text(json.dumps(metadata))
        return metadata

    def test_draft_package_cannot_allocate_a_ten_step_run(self):
        rejected = self.init()
        self.assertIn('qualified', rejected.stderr)
        self.assertIn('#9', rejected.stderr)

    def test_qualified_declaration_still_rejects_an_empty_released_request(self):
        metadata = self.qualified_fixture()
        (self.package / 'requests/10.txt').write_text(' \n')
        metadata['files']['requests/10.txt'] = hashlib.sha256(b' \n').hexdigest()
        (self.package / 'package.json').write_text(json.dumps(metadata))
        rejected = self.init()
        self.assertIn('nonempty', rejected.stderr)

    def test_matching_request_bytes_through_a_symlink_are_not_a_frozen_package(self):
        self.qualified_fixture()
        request = self.package / 'requests/10.txt'
        outside = self.base / 'outside-request.txt'
        outside.write_bytes(request.read_bytes())
        request.unlink()
        request.symlink_to(outside)
        rejected = self.init()
        self.assertIn('regular files', rejected.stderr)

    def test_qualified_declaration_freezes_ten_requests_but_waits_for_private_binding(self):
        self.qualified_fixture()
        self.init(success=True)
        run = self.runs / 'ten-steps'
        configuration = json.loads((run / 'configuration.json').read_text())
        sequence = json.loads((run / 'sequence.json').read_text())
        self.assertEqual(configuration['run_mode'], 'qualification')
        self.assertEqual(len(sequence['steps']), 10)
        self.assertEqual(configuration['evaluator_binding'], 'unbound')
        for number in range(1, 11):
            name = f'requests/{number:02}.txt'
            self.assertEqual((run / name).read_bytes(), (self.package / name).read_bytes())
        self.assertFalse((run / 'development').exists())
        status = subprocess.run([sys.executable, '-m', 'principiis', 'status',
                                 '--run', 'ten-steps', '--runs-root', str(self.runs),
                                 '--format', 'json'], cwd=self.source, capture_output=True, text=True)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)['next_action']['action'], 'bind-evaluator')


if __name__ == '__main__':
    unittest.main()
