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

    def generate_checkpoint(self, command=None):
        command = command or "from pathlib import Path; Path('app.py').write_text('print(42)')"
        process = subprocess.run([sys.executable, '-m', 'principiis.manual', 'develop',
            '--sequence', str(self.root / 'sequence.json'), '--output', str(self.root / 'development'),
            '--step', 'step-01', '--development-only', '--executor',
            json.dumps([sys.executable, '-c', command])],
            cwd=self.source, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_real_restricted_runner_failure_is_retained_and_rerun_is_explicit(self):
        # The actual restricted runner executes; image inspection fails at the
        # Docker boundary while cleanup succeeds. No candidate code runs on host.
        docker = self.base / 'unavailable-image-docker'
        docker.write_text('''#!/usr/bin/python3
import sys
args=sys.argv[1:]
if args[:1]==['--host']: args=args[2:]
if args[:1]==['rm']: print('no retained containers')
else:
 print('engineering unavailable image',file=sys.stderr)
 raise SystemExit(1)
''')
        docker.chmod(0o755)
        runtime = self.root / 'runtime.json'
        runtime.write_text(json.dumps({'image': self.image, 'docker': str(docker)}))
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

    def test_candidate_virtual_environment_packages_are_retained_before_runtime_launch(self):
        self.generate_checkpoint("""from pathlib import Path
root = Path('.venv/lib/python3.12/site-packages')
package = root / 'sample-1.2.dist-info'
package.mkdir(parents=True)
(package / 'METADATA').write_text('Metadata-Version: 2.1\\nName: sample\\nVersion: 1.2\\n')
Path('.venv/pyvenv.cfg').write_text('home = /usr/local/bin\\n')
Path('app.py').write_text('print(42)')
""")
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)
        assessed = self.cli('evaluate', '--step', 'step-01')
        self.assertEqual(assessed.returncode, 0, assessed.stderr)
        record = json.loads((self.root / 'development/evaluations/step-01/1/result.json').read_text())
        provenance = record['candidate_dependencies']
        self.assertEqual(provenance['environments'][0]['sites'][0]['packages'],
                         [{'name': 'sample', 'version': '1.2',
                           'metadata': '.venv/lib/python3.12/site-packages/sample-1.2.dist-info/METADATA',
                           'sha256': hashlib.sha256(b'Metadata-Version: 2.1\nName: sample\nVersion: 1.2\n').hexdigest()}])
        self.assertEqual(provenance['snapshot_manifest_sha256'], record['snapshot_manifest_sha256'])
        self.assertTrue(record['runtime_launch_attempted'])

    def test_uninventoried_candidate_virtual_environment_blocks_runtime_launch(self):
        self.generate_checkpoint("""from pathlib import Path
root = Path('.venv/lib/python3.12/site-packages')
root.mkdir(parents=True)
(root / 'unrecorded.egg-info').write_text('Name: unrecorded\\nVersion: 1\\n')
Path('.venv/pyvenv.cfg').write_text('home = /usr/local/bin\\n')
Path('app.py').write_text('print(42)')
""")
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)
        assessed = self.cli('evaluate', '--step', 'step-01')
        self.assertEqual(assessed.returncode, 0, assessed.stderr)
        record = json.loads((self.root / 'development/evaluations/step-01/1/result.json').read_text())
        self.assertEqual(record['outcome'], 'evaluator_error')
        self.assertFalse(record['runtime_launch_attempted'])
        self.assertIn('unsupported candidate dependency metadata', record['error'])

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

    def test_runtime_copy_grants_service_writes_without_changing_retained_modes(self):
        docker = self.base / 'permissions-docker'
        docker.write_text('''#!/usr/bin/python3
import json, pathlib, stat, sys
args=sys.argv[1:]
if args[:1]==['--host']: args=args[2:]
if args[:2]==['image','inspect']: print(json.dumps([{'Id':args[2]}]))
elif args[:1]==['run'] and '-d' in args:
 mount=next(arg for arg in args if 'dst=/workspace' in arg)
 root=pathlib.Path(mount.split('src=')[1].split(',')[0])
 writable=(bool(root.stat().st_mode & stat.S_IWOTH) and bool((root/'private.db').stat().st_mode & stat.S_IWOTH)
           and bool((root/'startup').stat().st_mode & stat.S_IXOTH)
           and not bool((root/'readonly').stat().st_mode & stat.S_IWOTH))
 print('service write granted' if writable else 'service write denied')
 sys.exit(0 if writable else 1)
else: print('{}')
''')
        docker.chmod(0o755)
        snapshot = self.base / 'snapshot'
        snapshot.mkdir(mode=0o700)
        (snapshot / 'private.db').write_bytes(b'retained sqlite control bytes')
        (snapshot / 'private.db').chmod(0o600)
        (snapshot / 'startup').write_text('#!/bin/sh\nexit 0\n')
        (snapshot / 'startup').chmod(0o700)
        (snapshot / 'readonly').write_text('read-only application data')
        (snapshot / 'readonly').chmod(0o400)
        output = self.base / 'permissions-assessment'
        process = subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(snapshot),
            '--output', str(output), '--app-image', self.image, '--evaluator-image', self.checker_image,
            '--docker', str(docker), '--app-command', '["python", "app.py"]'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads((output / 'assessment.json').read_text())
        launch = next(index for index, command in enumerate(result['commands']) if 'run' in command and '-d' in command)
        self.assertEqual(result['exit_statuses'][launch], 0)
        self.assertEqual(snapshot.stat().st_mode & 0o777, 0o700)
        self.assertEqual((snapshot / 'private.db').stat().st_mode & 0o777, 0o600)

    def test_interrupted_assessment_waits_for_detached_application_cleanup(self):
        import os
        import signal
        import time
        docker = self.base / 'interrupt-docker'
        docker.write_text('''#!/usr/bin/python3
import json, os, pathlib, signal, subprocess, sys, time
args=sys.argv[1:]
if args[:1]==['--host']: args=args[2:]
root=pathlib.Path(__file__).parent
if args[:2]==['image','inspect']: print(json.dumps([{'Id':args[2]}]))
elif args[:1]==['run'] and '-d' in args:
 worker="import pathlib,signal,sys,time; p=pathlib.Path(sys.argv[1]); signal.signal(signal.SIGTERM,lambda *_:(p.unlink(missing_ok=True),sys.exit(0))); p.write_text('active'); time.sleep(60)"
 child=subprocess.Popen([sys.executable,'-c',worker,str(root/'application-active')],
     start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 (root/'application-pid').write_text(str(child.pid))
 print('detached engineering application')
elif args[:1]==['exec']:
 (root/'check-running').write_text('ready to interrupt')
 time.sleep(60)
elif args[:1]==['rm']:
 time.sleep(.35)
 if args[-1].startswith('po-app-'):
  pid=int((root/'application-pid').read_text())
  try: os.kill(pid,signal.SIGTERM)
  except ProcessLookupError: pass
  deadline=time.monotonic()+3
  while (root/'application-active').exists() and time.monotonic()<deadline: time.sleep(.01)
 print('removed')
else: print('engineering lifecycle boundary')
''')
        docker.chmod(0o755)
        runtime = self.root / 'runtime.json'
        runtime.write_text(json.dumps({'image': self.image, 'docker': str(docker)}))
        self.configuration['frozen_files']['runtime.json'] = self.digest(runtime)
        (self.root / 'configuration.json').write_text(json.dumps(self.configuration))
        self.generate_checkpoint()
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)
        process = subprocess.Popen([sys.executable, '-m', 'principiis.assessment', 'evaluate',
                                   '--root', str(self.root), '--step', 'step-01'],
                                  cwd=self.source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (self.base / 'check-running').exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue((self.base / 'application-active').exists())
            self.assertTrue((self.base / 'check-running').exists())
            allocated = json.loads((self.root / 'development/evaluations/step-01/allocations.json').read_text())[0]
            process.terminate()
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertFalse((self.base / 'application-active').exists(), 'detached application survived interrupted assessment')
            result = json.loads((self.root / 'development/evaluations/step-01/1/result.json').read_text())
            self.assertEqual(result['session_id'], allocated['session_id'])
            self.assertEqual((result['role'], result['outcome']), ('primary', 'evaluator_error'))
            self.assertFalse(result['cleanup_pending'])
            self.assertFalse(result['evaluation']['termination']['forced'])
            restricted = json.loads(Path(result['evidence']).read_text())
            self.assertTrue(restricted['resources_removed'])
            self.assertIn('interrupt', restricted['error'])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            pid_file = self.base / 'application-pid'
            if pid_file.exists():
                try:
                    os.kill(int(pid_file.read_text()), signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def test_unresolved_runtime_cleanup_retains_container_identities(self):
        runtime = self.root / 'runtime.json'
        runtime.write_text(json.dumps({'image': self.image, 'docker': '/nonexistent/docker'}))
        self.configuration['frozen_files']['runtime.json'] = self.digest(runtime)
        (self.root / 'configuration.json').write_text(json.dumps(self.configuration))
        self.generate_checkpoint()
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)
        process = self.cli('evaluate', '--step', 'step-01')
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads((self.root / 'development/evaluations/step-01/1/result.json').read_text())
        self.assertTrue(result['cleanup_pending'])
        self.assertEqual(result['outcome'], 'evaluator_error')
        allocation = json.loads(Path(result['runtime_allocation']).read_text())
        self.assertFalse(allocation['resources_removed'])
        self.assertEqual(result['containers'], allocation['containers'])
        self.assertEqual(result['cleanup_argv'], allocation['cleanup_argv'])
        self.assertEqual(set(result['containers']), {'application', 'evaluator'})
        rejected = self.cli('evaluate', '--step', 'step-01', '--rerun')
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('cleanup', rejected.stderr)
        ledger = self.root / 'development/evaluations/step-01/allocations.json'
        self.assertEqual(len(json.loads(ledger.read_text())), 1)

    def test_candidate_copy_failure_does_not_require_runtime_cleanup(self):
        import resource
        self.generate_checkpoint("from pathlib import Path; Path('payload').write_bytes(b'x' * 262144)")
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)

        def limit_new_file_size():
            resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))

        command = [sys.executable, '-m', 'principiis.assessment', 'evaluate',
                   '--root', str(self.root), '--step', 'step-01']
        first = subprocess.run(command, cwd=self.source, capture_output=True, text=True,
                               preexec_fn=limit_new_file_size)
        self.assertEqual(first.returncode, 0, first.stderr)
        result_path = self.root / 'development/evaluations/step-01/1/result.json'
        original = result_path.read_bytes()
        result = json.loads(original)
        self.assertEqual(result['outcome'], 'evaluator_error')
        self.assertIn('File too large', result['error'])
        self.assertFalse(result['cleanup_pending'])
        self.assertEqual(result['evaluation'], {})
        self.assertFalse(Path(result['evidence']).parent.exists())
        inspected = self.cli('inspect')
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout)['cleanup_required'], [])
        rerun = subprocess.run([*command, '--rerun'], cwd=self.source,
                               capture_output=True, text=True, preexec_fn=limit_new_file_size)
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertEqual(result_path.read_bytes(), original)
