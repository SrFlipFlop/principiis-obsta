"""Engineering controls at the explicit binding/retained-assessment seam."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AssessmentCLI(unittest.TestCase):
    def test_unqualified_release_cannot_bind_or_allocate_an_assessment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'configuration.json').write_text(json.dumps({'application': 'document-portal'}))
            declaration = root / 'declaration.json'
            declaration.write_text('{}')
            process = subprocess.run([sys.executable, '-m', 'principiis.assessment', 'bind',
                                      '--root', str(root), '--declaration', str(declaration)],
                                     cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn('qualified', process.stderr)
            self.assertFalse((root / 'evaluator-binding.json').exists())
            self.assertFalse((root / 'development/evaluations').exists())


class QualifiedAssessmentCLI(unittest.TestCase):
    def setUp(self):
        import shutil
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        shutil.copytree(ROOT / 'principiis', self.source / 'principiis', ignore=shutil.ignore_patterns('__pycache__'))
        self.package = self.source / 'benchmarks/document-portal'
        self.package.mkdir(parents=True)
        self.root = self.base / 'run'
        self.root.mkdir()
        (self.root / 'requests').mkdir()
        (self.root / 'requests/01.txt').write_text('Engineering control requirements')
        self.image = 'sha256:' + 'a' * 64
        self.checker_image = 'sha256:' + 'b' * 64
        (self.root / 'runtime.json').write_text(json.dumps({'image': self.image}))
        (self.root / 'sequence.json').write_text(json.dumps({'id': 'document-portal', 'version': 'fixture',
            'condition': {'id': 'ordinary', 'version': '1'}, 'steps': [{'id': 'step-01', 'version': 'fixture',
            'sequence_version': 'fixture', 'request': 'requests/01.txt'}]}))
        self.configuration = {'application': 'document-portal', 'run_name': 'control',
            'package_version': 'fixture', 'frozen_files': {name: self.digest(self.root / name)
            for name in ('runtime.json', 'sequence.json', 'requests/01.txt')}}
        (self.root / 'configuration.json').write_text(json.dumps(self.configuration))
        self.bundle = self.base / 'private'
        self.bundle.mkdir()
        (self.bundle / 'contract.json').write_text(json.dumps({'browser-read': 'functional', 'backend-denial': 'security'}))
        (self.bundle / 'seccomp.json').write_text('{}')
        (self.bundle / 'preparation.json').write_text('{"kind":"engineering control preparation receipt"}')
        (self.bundle / 'dependencies.json').write_text(json.dumps({'complete': True, 'images': {
            self.image: {'packages': [{'name': 'python', 'version': '3.12'}], 'preparation_evidence': ['preparation.json']},
            self.checker_image: {'packages': [{'name': 'playwright', 'version': '1.56.1'}], 'preparation_evidence': ['preparation.json']}}}))
        self.declaration = {'version': 'engineering-1', 'complete': True, 'qualification_status': 'qualified',
            'owner_review': 'approved', 'requests': {'requests/01.txt': self.digest(self.root / 'requests/01.txt')},
            'runtime_image': self.image, 'evaluator_images': {'step-01': self.checker_image},
            'seccomp': 'seccomp.json', 'dependency_manifest': 'dependencies.json',
            'steps': {'step-01': {'contract': 'contract.json', 'app_command': ['python', '/workspace/app.py']}},
            'files': {path.name: self.digest(path) for path in self.bundle.iterdir()}}
        (self.package / 'requests').mkdir()
        (self.package / 'requests/01.txt').write_bytes((self.root / 'requests/01.txt').read_bytes())
        self.publish()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def publish(self):
        self.path = self.bundle / 'bundle.json'
        self.path.write_text(json.dumps(self.declaration))
        (self.package / 'package.json').write_text(json.dumps({'id': 'document-portal', 'version': 'fixture',
            'qualification_status': 'qualified', 'owner_review': 'approved',
            'private_bundle_sha256': self.digest(self.path), 'files': {'requests/01.txt': self.digest(self.package / 'requests/01.txt')}}))

    def cli(self, *arguments):
        return subprocess.run([sys.executable, '-m', 'principiis.assessment', *arguments,
                               '--root', str(self.root)], cwd=self.source, capture_output=True, text=True)

    def test_binding_freezes_complete_evaluator_separately_from_development(self):
        before = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        process = self.cli('bind', '--declaration', str(self.path))
        self.assertEqual(process.returncode, 0, process.stderr)
        binding = json.loads((self.root / 'evaluator-binding.json').read_text())
        self.assertEqual(binding['manifest_sha256'], self.digest(self.path))
        self.assertEqual(binding['version'], 'engineering-1')
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents)
        self.assertFalse((self.root / 'development').exists())

    def test_bound_assessment_rejects_changed_dependency_before_allocating(self):
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)
        (self.bundle / 'preparation.json').write_text('changed after binding')
        process = self.cli('evaluate', '--step', 'step-01')
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('dependency content changed', process.stderr)
        self.assertFalse((self.root / 'development/evaluations').exists())

    def test_restricted_runner_accepts_bound_links_without_following_host_targets(self):
        from principiis.snapshot import preserve
        workspace = self.base / 'workspace'
        workspace.mkdir()
        (workspace / 'app.py').write_text('raise SystemExit("must run in container")')
        (workspace / 'python').symlink_to('/usr/local/bin/python3.12')
        snapshot = self.base / 'snapshot'
        preserve(workspace, snapshot, runtime_binding={'image': self.image,
                 'symlink_targets': ['/usr/local/bin/python3.12']})
        output = self.base / 'assessment'
        process = subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(snapshot),
            '--output', str(output), '--app-image', self.image, '--evaluator-image', self.checker_image,
            '--app-command', json.dumps(['/workspace/python', '/workspace/app.py']), '--docker', '/nonexistent/docker'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads((output / 'assessment.json').read_text())
        self.assertTrue(result['snapshot_sha256'])
        self.assertTrue(result['snapshot_unchanged'])
        self.assertEqual(result['outcome'], 'evaluator_error')
        self.assertIn('No such file', result['error'])
        self.assertTrue((snapshot / 'python').is_symlink())

    def generate_checkpoint(self):
        process = subprocess.run([sys.executable, '-m', 'principiis.manual', 'develop',
            '--sequence', str(self.root / 'sequence.json'), '--output', str(self.root / 'development'),
            '--step', 'step-01', '--development-only', '--executor',
            json.dumps([sys.executable, '-c', "from pathlib import Path; Path('app.py').write_text('print(42)')"])],
            cwd=self.source, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_real_restricted_runner_failure_is_retained_and_rerun_is_explicit(self):
        # The actual restricted runner executes; a nonexistent Docker executable
        # produces infrastructure evidence without running candidate code on host.
        runtime = self.root / 'runtime.json'
        runtime.write_text(json.dumps({'image': self.image, 'docker': '/nonexistent/docker'}))
        self.configuration['frozen_files']['runtime.json'] = self.digest(runtime)
        (self.root / 'configuration.json').write_text(json.dumps(self.configuration))
        self.generate_checkpoint()
        original = {path: path.read_bytes() for path in (self.root / 'development/steps/step-01').rglob('*') if path.is_file()}
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)
        process = self.cli('evaluate', '--step', 'step-01')
        self.assertEqual(process.returncode, 0, process.stderr)
        primary = self.root / 'development/evaluations/step-01/1/result.json'
        first = primary.read_bytes()
        result = json.loads(first)
        self.assertEqual((result['outcome'], result['functional'], result['security']),
                         ('evaluator_error', 'unassessable', 'unassessable'))
        self.assertGreater(result['evaluation']['elapsed_seconds'], 0)
        self.assertIsNone(result['evaluation']['tokens'])
        self.assertTrue(Path(result['evidence']).is_file())
        repeated = self.cli('evaluate', '--step', 'step-01')
        self.assertNotEqual(repeated.returncode, 0)
        self.assertIn('--rerun', repeated.stderr)
        rerun = self.cli('evaluate', '--step', 'step-01', '--rerun')
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertEqual(primary.read_bytes(), first)
        self.assertEqual(json.loads((primary.parent.parent / '2/result.json').read_text())['role'], 'rerun')
        for path, contents in original.items():
            self.assertEqual(path.read_bytes(), contents)

    def test_retained_binding_remains_readable_after_author_release_changes(self):
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)
        (self.package / 'package.json').write_text('{"version":"later-draft"}')
        self.path.unlink()
        process = self.cli('inspect')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['binding']['version'], 'engineering-1')

    def test_assessment_cannot_be_repointed_away_from_completed_checkpoint(self):
        runtime = self.root / 'runtime.json'
        runtime.write_text(json.dumps({'image': self.image, 'docker': '/nonexistent/docker'}))
        self.configuration['frozen_files']['runtime.json'] = self.digest(runtime)
        (self.root / 'configuration.json').write_text(json.dumps(self.configuration))
        self.generate_checkpoint()
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)
        self.assertEqual(self.cli('evaluate', '--step', 'step-01').returncode, 0)
        parent = self.root / 'development/evaluations/step-01'
        result = json.loads((parent / '1/result.json').read_text())
        ledger = json.loads((parent / 'allocations.json').read_text())
        result['developer_result_sha256'] = ledger[0]['developer_result_sha256'] = '0' * 64
        (parent / '1/result.json').write_text(json.dumps(result))
        (parent / 'allocations.json').write_text(json.dumps(ledger))
        process = self.cli('inspect')
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('completed development', process.stderr)

    def test_executed_check_vectors_keep_unassessable_and_missing_checks_distinct(self):
        docker = self.base / 'docker'
        docker.write_text('''#!/usr/bin/python3
import json, pathlib, sys
args=sys.argv[1:]
if args[:1]==['--host']: args=args[2:]
if args[:2]==['image','inspect']:
 print(json.dumps([{'Id':args[2]}]))
elif args[:1]==['exec']:
 print(json.dumps({'uid':1000,'hidden_visible':False,
 'status':'CapEff:\\t0000000000000000 NoNewPrivs:\\t1 Seccomp:\\t2',
 'limits':{'memory.max':'1073741824','memory.swap.max':'0','pids.max':'256','cpu.max':'100000 100000'},
 'namespaces':{'net':'shared','pid':'application','mnt':'application'}}))
elif args[:1]==['run'] and 'node' in args:
 mount=next(arg for arg in args if 'dst=/evidence' in arg)
 evidence=pathlib.Path(mount.split('src=')[1].split(',')[0])
 checks=[{'id':'browser-read','kind':'functional','status':'pass'},
         {'id':'backend-denial','kind':'security','status':'unassessable'}]
 if pathlib.Path(__file__).with_name('mode').read_text()=='missing': checks=checks[:1]
 (evidence/'checks.json').write_text(json.dumps({'checks':checks,
 'diagnostics':{'namespaces':{'net':'shared','pid':'evaluator','mnt':'evaluator'}}}))
 (evidence/'trace.zip').write_bytes(b'engineering trace fixture')
else: print('engineering Docker boundary fixture')
''')
        docker.chmod(0o755)
        (self.base / 'mode').write_text('unassessable')
        snapshot = self.base / 'snapshot'
        snapshot.mkdir()
        (snapshot / 'app.py').write_text('raise SystemExit("must never execute on host")')
        for mode, expected in [('unassessable', 'unassessable'), ('missing', 'evaluator_error')]:
            (self.base / 'mode').write_text(mode)
            output = self.base / mode
            process = subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(snapshot),
                '--output', str(output), '--app-image', self.image, '--evaluator-image', self.checker_image,
                '--check-contract', str(self.bundle / 'contract.json'), '--docker', str(docker)],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads((output / 'assessment.json').read_text())
            self.assertEqual(result['outcome'], expected, result.get('error'))
            self.assertEqual(result['security'], 'unassessable')
            self.assertTrue((output / 'trace.zip').exists())
