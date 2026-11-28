"""Engineering controls at the evaluator binding and restricted assessment seam."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from support import FIXTURE_CONTRACT, NODE_ORACLE, attempt_files, create_run, temporary_directory
import fixture_runtime
import unittest

from principiis.assessment import bind
from principiis.run_store import RunStore

ROOT = Path(__file__).resolve().parents[1]
REQUEST = 'Engineering control requirements'


class AssessmentCLI(unittest.TestCase):
    def test_unqualified_release_cannot_bind_or_allocate_an_assessment(self):
        with temporary_directory() as temporary:
            store = create_run(Path(temporary) / 'run')
            declaration = Path(temporary) / 'declaration.json'
            declaration.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'qualified'):
                bind(store, declaration)
            reopened = RunStore.open(store.root)
            self.assertIsNone(reopened.binding)
            self.assertEqual(reopened.assessments, [])


class QualifiedAssessmentCLI(unittest.TestCase):
    """A copied controller checkout with a fixture package and private bundle; no model, no real Docker."""

    def setUp(self):
        self.temporary = temporary_directory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        shutil.copytree(ROOT / 'principiis', self.source / 'principiis', ignore=shutil.ignore_patterns('__pycache__'))
        self.package = self.source / 'benchmarks/document-portal'
        (self.package / 'requests').mkdir(parents=True)
        (self.package / 'requests/01.txt').write_text(REQUEST)
        self.root = self.base / 'run'
        self.image = 'sha256:' + 'a' * 64
        self.checker_image = 'sha256:' + 'b' * 64
        self.bundle = self.base / 'private'
        self.bundle.mkdir()
        (self.bundle / 'contract.json').write_text(json.dumps({'browser-read': 'functional', 'backend-denial': 'security'}))
        (self.bundle / 'seccomp.json').write_text('{}')
        (self.bundle / 'preparation.json').write_text('{"kind":"engineering control preparation receipt"}')
        (self.bundle / 'dependencies.json').write_text(json.dumps({'complete': True, 'images': {
            self.image: {'packages': [{'name': 'python', 'version': '3.12'}], 'preparation_evidence': ['preparation.json']},
            self.checker_image: {'packages': [{'name': 'playwright', 'version': '1.56.1'}], 'preparation_evidence': ['preparation.json']}}}))
        self.declaration = {'version': 'engineering-1', 'complete': True,
            'requests': {'requests/01.txt': self.digest(self.package / 'requests/01.txt')},
            'runtime_image': self.image, 'evaluator_images': {'step-01': self.checker_image},
            'seccomp': 'seccomp.json', 'dependency_manifest': 'dependencies.json',
            'steps': {'step-01': {'contract': 'contract.json', 'app_command': ['python', '/workspace/app.py']}},
            'files': {path.name: self.digest(path) for path in self.bundle.iterdir()}}
        self.publish()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def publish(self, **package):
        self.path = self.bundle / 'bundle.json'
        self.path.write_text(json.dumps(self.declaration))
        (self.package / 'package.json').write_text(json.dumps(dict({
            'id': 'document-portal', 'version': 'fixture', 'steps': 1, 'qualified_through': 1,
            'private_bundle_sha256': self.digest(self.path),
            'files': {'requests/01.txt': self.digest(self.package / 'requests/01.txt')}}, **package)))

    def make_run(self, runtime=None, name='run', requests=(REQUEST,), **configuration):
        return create_run(self.base / name, requests=list(requests),
                          runtime=runtime or {'image': self.image, 'docker': '/nonexistent/docker'}, **configuration)

    def record(self, path):
        """A retained run record named by operator output, read through the run store."""
        return RunStore(self.root).record(path)

    def bind(self, name='run'):
        return bind(RunStore.open(self.base / name), self.path, package=self.package)

    def operator(self, command, *arguments, run='run', success=True, **options):
        """The operator CLI of the copied checkout, with JSON output."""
        process = subprocess.run([sys.executable, '-m', 'principiis', command, '--run', run,
                                  '--runs-root', str(self.base), '--format', 'json', *arguments],
                                 cwd=self.source, capture_output=True, text=True, **options)
        if success is None:
            return process
        if success:
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)
        self.assertNotEqual(process.returncode, 0, process.stdout)
        return process

    def generate_checkpoint(self, command=None):
        command = command or "from pathlib import Path; Path('app.py').write_text('print(42)')"
        runtime = self.base / 'fixture-runtime.json'
        runtime.write_text(json.dumps({'argv': [sys.executable, '-c', command]}))
        fixture_runtime.develop(self.root, 'step-01', runtime)

    def test_binding_freezes_complete_evaluator_separately_from_development(self):
        self.make_run()
        before = RunStore.open(self.root).configuration
        self.bind()
        # Opening verifies every frozen input against the unchanged freeze manifest.
        store = RunStore.open(self.root)
        self.assertEqual(store.binding['manifest_sha256'], self.digest(self.path))
        self.assertEqual(store.binding['version'], 'engineering-1')
        self.assertEqual(store.configuration, before)
        self.assertEqual(store.attempts, [])

    def test_release_binds_only_within_its_qualified_steps(self):
        requests = [REQUEST, 'Engineering request 2', 'Engineering request 3']
        for number in (2, 3):
            name = f'requests/{number:02}.txt'
            (self.package / name).write_text(requests[number - 1])
            self.declaration['requests'][name] = self.digest(self.package / name)
            self.declaration['evaluator_images'][f'step-{number:02}'] = self.checker_image
            self.declaration['steps'][f'step-{number:02}'] = self.declaration['steps']['step-01']
        files = {name: self.digest(self.package / name) for name in self.declaration['requests']}
        self.publish(steps=3, qualified_through=3, files=files)
        self.make_run(requests=requests)
        self.bind()
        self.assertTrue(RunStore.open(self.root).binding)
        self.publish(steps=3, qualified_through=2, files=files)
        self.make_run(name='second', requests=requests)
        with self.assertRaisesRegex(ValueError, 'qualified through step 2'):
            self.bind('second')

    def evaluated(self):
        self.make_run()
        self.generate_checkpoint()
        self.bind()
        return self.operator('evaluate', '--step', '1')['assessments'][0]

    def test_declared_evaluator_command_runs_in_the_evaluator_image(self):
        self.declaration['evaluator_command'] = ['python3', '/checks/run.py']
        self.publish()
        evidence = self.record(self.evaluated()['evidence'])
        self.assertEqual(evidence['evaluator_command'], ['python3', '/checks/run.py'])

    def test_declaration_predating_evaluator_command_keeps_node_oracle_and_binds_unchanged(self):
        # Declarations frozen before #68 also carried owner-review fields; they bind as before.
        self.declaration.update(qualification_status='qualified_first_three', owner_review='approved_first_three')
        self.publish()
        evidence = self.record(self.evaluated()['evidence'])
        self.assertEqual(evidence['evaluator_command'], ['node', '/oracle/check.cjs'])
        binding = RunStore.open(self.root).binding
        self.assertEqual(binding['manifest_sha256'], self.digest(self.path))
        self.assertEqual(binding['declaration'], self.declaration)

    def test_assessment_records_the_controller_commit_instead_of_source_hashes(self):
        assessment = self.evaluated()
        self.assertIn('commit', assessment['controller'])
        self.assertNotIn('controller_sources', assessment)
        self.assertNotIn('sha256', assessment['python_executable'])

    def test_bound_assessment_rejects_changed_checks_before_allocating(self):
        self.make_run()
        self.generate_checkpoint()
        self.bind()
        # #75: the run evaluates its own hash-checked copy, so tampering targets the copy.
        (self.root / 'evaluator/contract.json').write_text(json.dumps({'other': 'functional', 'denial': 'security'}))
        process = self.operator('evaluate', '--step', '1', success=False)
        self.assertIn('dependency content changed', process.stderr)
        self.assertEqual(self.operator('status')['assessments'], [])

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
            '--app-command', json.dumps(['/workspace/python', '/workspace/app.py']), '--docker', '/nonexistent/docker',
            *FIXTURE_CONTRACT, *NODE_ORACLE],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads((output / 'assessment.json').read_text())
        self.assertTrue(result['snapshot_sha256'])
        self.assertTrue(result['snapshot_unchanged'])
        self.assertEqual(result['outcome'], 'evaluator_error')
        self.assertIn('No such file', result['error'])
        self.assertTrue((snapshot / 'python').is_symlink())

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
        self.make_run({'image': self.image, 'docker': str(docker)})
        self.generate_checkpoint()
        original = attempt_files(self.root)
        self.bind()
        result = self.operator('evaluate', '--step', '1')['assessments'][0]
        self.assertEqual((result['outcome'], result['functional'], result['security']),
                         ('evaluator_error', 'unassessable', 'unassessable'))
        self.assertGreater(result['evaluation']['elapsed_seconds'], 0)
        self.assertIsNone(result['evaluation']['tokens'])
        self.assertTrue(Path(result['evidence']).is_file())
        repeated = self.operator('evaluate', '--step', '1', success=False)
        self.assertIn('--rerun', repeated.stderr)
        rerun = self.operator('evaluate', '--step', '1', '--rerun')
        self.assertEqual(rerun['assessments'][0], result)
        self.assertEqual(rerun['assessments'][1]['role'], 'rerun')
        self.assertEqual(attempt_files(self.root), original)

    def test_candidate_virtual_environment_packages_are_retained_before_runtime_launch(self):
        self.make_run()
        self.generate_checkpoint("""from pathlib import Path
root = Path('.venv/lib/python3.12/site-packages')
package = root / 'sample-1.2.dist-info'
package.mkdir(parents=True)
(package / 'METADATA').write_text('Metadata-Version: 2.1\\nName: sample\\nVersion: 1.2\\n')
Path('.venv/pyvenv.cfg').write_text('home = /usr/local/bin\\n')
Path('app.py').write_text('print(42)')
""")
        self.bind()
        record = self.operator('evaluate', '--step', '1')['assessments'][0]
        provenance = record['candidate_dependencies']
        self.assertEqual(provenance['environments'][0]['sites'][0]['packages'],
                         [{'name': 'sample', 'version': '1.2',
                           'metadata': '.venv/lib/python3.12/site-packages/sample-1.2.dist-info/METADATA',
                           'sha256': hashlib.sha256(b'Metadata-Version: 2.1\nName: sample\nVersion: 1.2\n').hexdigest()}])
        self.assertEqual(provenance['snapshot_manifest_sha256'], record['snapshot_manifest_sha256'])
        self.assertTrue(record['runtime_launch_attempted'])

    def test_uninventoried_candidate_virtual_environment_blocks_runtime_launch(self):
        self.make_run()
        self.generate_checkpoint("""from pathlib import Path
root = Path('.venv/lib/python3.12/site-packages')
root.mkdir(parents=True)
(root / 'unrecorded.egg-info').write_text('Name: unrecorded\\nVersion: 1\\n')
Path('.venv/pyvenv.cfg').write_text('home = /usr/local/bin\\n')
Path('app.py').write_text('print(42)')
""")
        self.bind()
        record = self.operator('evaluate', '--step', '1')['assessments'][0]
        self.assertEqual(record['outcome'], 'evaluator_error')
        self.assertFalse(record['runtime_launch_attempted'])
        self.assertIn('unsupported candidate dependency metadata', record['error'])

    def test_retained_binding_remains_readable_after_author_release_changes(self):
        self.make_run()
        self.bind()
        (self.package / 'package.json').write_text('{"version":"later-draft"}')
        self.path.unlink()
        self.assertEqual(self.operator('status')['assessment_binding']['version'], 'engineering-1')

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
                '--check-contract', str(self.bundle / 'contract.json'), *NODE_ORACLE, '--docker', str(docker)],
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
            '--docker', str(docker), '--app-command', '["python", "app.py"]', *FIXTURE_CONTRACT, *NODE_ORACLE],
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
        self.make_run({'image': self.image, 'docker': str(docker)})
        self.generate_checkpoint()
        self.bind()
        process = subprocess.Popen([sys.executable, '-m', 'principiis', 'evaluate', '--run', 'run',
                                    '--runs-root', str(self.base), '--step', '1', '--format', 'json'],
                                  cwd=self.source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (self.base / 'check-running').exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue((self.base / 'application-active').exists())
            self.assertTrue((self.base / 'check-running').exists())
            allocated = self.operator('status')['assessments'][0]
            process.terminate()
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertFalse((self.base / 'application-active').exists(), 'detached application survived interrupted assessment')
            result = json.loads(stdout)['assessments'][0]
            self.assertEqual(result['session_id'], allocated['session_id'])
            self.assertEqual((result['role'], result['outcome']), ('primary', 'evaluator_error'))
            self.assertFalse(result['cleanup_pending'])
            self.assertFalse(result['evaluation']['termination']['forced'])
            restricted = self.record(result['evidence'])
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
        self.make_run()
        self.generate_checkpoint()
        self.bind()
        result = self.operator('evaluate', '--step', '1')['assessments'][0]
        self.assertTrue(result['cleanup_pending'])
        self.assertEqual(result['outcome'], 'evaluator_error')
        allocation = self.record(result['runtime_allocation'])
        self.assertFalse(allocation['resources_removed'])
        self.assertEqual(result['containers'], allocation['containers'])
        self.assertEqual(result['cleanup_argv'], allocation['cleanup_argv'])
        self.assertEqual(set(result['containers']), {'application', 'evaluator'})
        rejected = self.operator('evaluate', '--step', '1', '--rerun', success=False)
        self.assertIn('cleanup', rejected.stderr)
        self.assertEqual(len(self.operator('status')['assessments']), 1)

    def test_candidate_copy_failure_does_not_require_runtime_cleanup(self):
        import resource
        self.make_run()
        self.generate_checkpoint("from pathlib import Path; Path('payload').write_bytes(b'x' * 262144)")
        self.bind()

        def limit_new_file_size():
            resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))

        result = self.operator('evaluate', '--step', '1', preexec_fn=limit_new_file_size)['assessments'][0]
        self.assertEqual(result['outcome'], 'evaluator_error')
        self.assertIn('File too large', result['error'])
        self.assertFalse(result['cleanup_pending'])
        self.assertEqual(result['evaluation'], {})
        self.assertFalse(Path(result['evidence']).parent.exists())
        self.assertEqual(self.operator('status')['evaluation_cleanup_required'], [])
        rerun = self.operator('evaluate', '--step', '1', '--rerun', preexec_fn=limit_new_file_size)
        self.assertEqual(rerun['assessments'][0], result)


if __name__ == '__main__':
    unittest.main()
