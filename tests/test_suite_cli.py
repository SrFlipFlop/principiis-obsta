import json
import os
import signal
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SuiteCLI(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.output = self.base / 'output'
        (self.base / 'request.txt').write_text('build')
        (self.base / 'check.py').write_text("print('{\"functional\":\"pass\",\"security\":\"pass\"}')")
        (self.base / 'executor.py').write_text("import pathlib,sys; sys.stdin.read(); pathlib.Path('app').write_text('candidate')")
        self.executor = json.dumps([sys.executable, str(self.base / 'executor.py')])
        for app in ('alpha', 'beta'):
            sequence = {'id': app, 'version': '1', 'condition': {'id': 'ordinary', 'version': '1'}, 'steps': [
                {'id': 'one', 'version': '1', 'sequence_version': '1', 'request': 'request.txt', 'check': [sys.executable, 'check.py']}]}
            (self.base / (app + '.json')).write_text(json.dumps(sequence))
        (self.base / 'suite.json').write_text(json.dumps({'id': 'fixture', 'version': '1', 'applications': [
            {'id': app, 'sequence': app + '.json'} for app in ('alpha', 'beta')]}))

    def cli(self, command, *options, success=True):
        argv = [sys.executable, '-m', 'principiis.suite', command, '--output', str(self.output)]
        if command == 'run':
            argv += ['--suite', str(self.base / 'suite.json'), '--executor', self.executor]
        process = subprocess.run(argv + list(options), cwd=ROOT, text=True, capture_output=True)
        if success:
            self.assertEqual(process.returncode, 0, process.stderr)
        else:
            self.assertNotEqual(process.returncode, 0)
        return process

    def report(self):
        return json.loads(self.cli('report').stdout)

    def test_sigterm_retains_attempt_measurements_and_kills_executor(self):
        (self.base / 'executor.py').write_text("import os,pathlib,sys,time; sys.stdin.read(); pathlib.Path('pid').write_text(str(os.getpid())); print('started',flush=True); time.sleep(60)")
        process = subprocess.Popen([sys.executable, '-m', 'principiis.suite', 'run',
            '--suite', str(self.base / 'suite.json'), '--executor', self.executor,
            '--output', str(self.output)], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        child = None
        try:
            artifact = self.output / 'applications/alpha/steps/one'
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                log = artifact / 'executor.stdout'
                if log.exists() and 'started' in log.read_text():
                    child = int((artifact / 'workspace/pid').read_text())
                    break
                time.sleep(.02)
            else:
                self.fail('executor did not reach interruption boundary')
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=5)
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)
            result = json.loads((artifact / 'result.json').read_text())
            self.assertEqual(result['outcome'], 'incomplete')
            self.assertGreater(result['execution']['elapsed_seconds'], 0)
            self.assertIn('interrupt', result['execution']['error'])
            self.assertEqual(self.report()['outcomes']['incomplete'], 1)
            self.assertFalse((self.output / 'applications/beta').exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if child is not None:
                try:
                    os.killpg(child, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_sigterm_during_first_evaluation_retains_checkpoint_and_stops_sequence(self):
        path = self.base / 'alpha.json'
        sequence = json.loads(path.read_text())
        sequence['steps'].append(dict(sequence['steps'][0], id='two'))
        path.write_text(json.dumps(sequence))
        (self.base / 'check.py').write_text("import time; print('evaluating',flush=True); time.sleep(60)")
        process = subprocess.Popen([sys.executable, '-m', 'principiis.suite', 'run',
            '--suite', str(self.base / 'suite.json'), '--executor', self.executor,
            '--output', str(self.output)], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            artifact = self.output / 'applications/alpha/steps/one'
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                log = artifact / 'evaluator.stdout'
                if log.exists() and 'evaluating' in log.read_text():
                    break
                time.sleep(.02)
            else:
                self.fail('evaluator did not reach interruption boundary')
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse((self.output / 'applications/alpha/steps/two').exists())
            self.assertFalse((self.output / 'applications/beta').exists())
            result = json.loads((artifact / 'result.json').read_text())
            self.assertTrue(result['completed'])
            self.assertEqual(result['outcome'], 'evaluator_error')
            self.assertTrue((artifact / 'snapshot/app').exists())
            self.assertGreater(result['evaluation']['elapsed_seconds'], 0)
            report = self.report()
            self.assertEqual(report['applications'][0]['status'], 'interrupted')
            self.assertEqual(report['denominators']['completed_checkpoints'], 1)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_executor_configuration_errors_are_retained_for_each_application(self):
        config = self.base / 'config.json'
        config.write_text('{}')
        process = subprocess.run([sys.executable, '-m', 'principiis.suite', 'run',
            '--suite', str(self.base / 'suite.json'), '--codex-config', str(config),
            '--output', str(self.output)], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(process.returncode, 0)
        errors = self.report()['controller_errors']
        self.assertEqual({error['application'] for error in errors}, {'alpha', 'beta'})
        self.assertTrue(all('configuration' in error['error'] for error in errors))

    def test_evaluator_preparation_failure_is_retained_and_other_app_continues(self):
        self.cli('run')
        (self.output / 'applications/alpha/tasks/one.json').unlink()
        self.cli('evaluate', '--evaluator-version', 'v2')
        assessments = self.report()['evaluations']
        self.assertEqual([a['outcome'] for a in assessments], ['evaluator_error', 'joint_pass'])
        self.assertEqual(assessments[0]['security'], 'unassessable')
        self.assertIn('error', assessments[0])

    def test_partial_suite_selection_continuation_and_no_regeneration(self):
        self.cli('run', '--application', 'alpha')
        first = (self.output / 'applications/alpha/steps/one/result.json').read_bytes()
        report = self.report()
        self.assertEqual(report['denominators'], {'planned_checkpoints': 2, 'completed_checkpoints': 1, 'unstarted_checkpoints': 1, 'attempts': 1})
        self.assertEqual(report['outcomes']['joint_pass'], 1)
        self.cli('run', '--application', 'beta', '--resume')
        self.assertEqual((self.output / 'applications/alpha/steps/one/result.json').read_bytes(), first)
        self.assertEqual(self.report()['denominators']['completed_checkpoints'], 2)
        self.cli('run', '--resume')
        self.assertEqual(self.report()['denominators']['attempts'], 2)

    def test_retry_preserves_incomplete_and_reports_unknown_security(self):
        (self.base / 'executor.py').write_text("import pathlib,sys; sys.stdin.read(); pathlib.Path('partial').touch(); sys.exit(0 if pathlib.Path(__file__).with_name('proceed').exists() else 7)")
        self.cli('run', '--application', 'alpha')
        original = (self.output / 'applications/alpha/steps/one/result.json').read_bytes()
        self.assertEqual(self.report()['outcomes']['incomplete'], 1)
        self.assertEqual(self.report()['security']['unknown'], 1)
        self.cli('run', '--application', 'alpha', '--resume', success=False)
        (self.base / 'proceed').touch()
        self.cli('run', '--application', 'alpha', '--resume', '--retry-incomplete')
        report = self.report()
        self.assertEqual(report['denominators']['attempts'], 2)
        self.assertEqual(report['outcomes']['incomplete'], 1)
        self.assertEqual(report['outcomes']['joint_pass'], 1)
        self.assertEqual((self.output / 'applications/alpha/steps/one/result.json').read_bytes(), original)
        self.assertEqual(report['resources']['totals']['development']['attempts_present'], 2)

    def test_rerun_evaluation_preserves_primary_and_retains_errors(self):
        self.cli('run', '--application', 'alpha')
        primary = self.output / 'applications/alpha/steps/one/result.json'
        before = primary.read_bytes()
        (self.base / 'check.py').write_text("print('{\"functional\":\"pass\",\"security\":\"fail\"}')")
        self.cli('evaluate', '--application', 'alpha', '--evaluator-version', 'v2')
        (self.base / 'check.py').write_text('raise RuntimeError("broken oracle")')
        self.cli('evaluate', '--application', 'alpha', '--evaluator-version', 'v3')
        report = self.report()
        self.assertEqual(primary.read_bytes(), before)
        self.assertEqual(report['outcomes']['joint_pass'], 1)
        self.assertEqual([r['outcome'] for r in report['evaluations']], ['candidate_failure', 'evaluator_error'])
        self.assertEqual(report['evaluations'][1]['security'], 'unassessable')
        self.assertEqual(report['resources']['totals']['development']['attempts_present'], 1)
        self.assertEqual(len(report['supplemental_resources']['evaluation_reruns']), 2)

    def test_candidate_and_evaluator_failures_remain_distinct(self):
        (self.base / 'check.py').write_text("print('{\"functional\":\"fail\",\"security\":\"pass\"}')")
        self.cli('run', '--application', 'alpha')
        (self.base / 'check.py').write_text('raise RuntimeError("bad oracle")')
        self.cli('run', '--application', 'beta', '--resume')
        report = self.report()
        self.assertEqual(report['outcomes']['candidate_failure'], 1)
        self.assertEqual(report['outcomes']['evaluator_error'], 1)
        self.assertEqual(report['security']['unknown'], 1)

    def test_candidate_named_artifacts_are_not_controller_resource_evidence(self):
        (self.base / 'executor.py').write_text("import pathlib,sys; sys.stdin.read(); pathlib.Path('result.json').write_text('candidate-controlled')")
        self.cli('run', '--application', 'alpha')
        self.assertEqual(len(self.report()['resources']['attempts']), 1)

    def test_invalid_selection_or_changed_suite_is_rejected(self):
        self.cli('run', '--application', '../escape', success=False)
        self.assertFalse(self.output.exists())
        self.cli('run', '--application', 'alpha')
        path = self.base / 'suite.json'
        data = json.loads(path.read_text())
        data['version'] = '2'
        path.write_text(json.dumps(data))
        self.cli('run', '--resume', success=False)

    def test_supplementary_claims_deduplicate_within_application_only(self):
        self.cli('run')
        for app in ('alpha', 'beta'):
            for number in range(2):
                destination = self.output / 'applications' / app / 'investigations' / str(number)
                destination.mkdir(parents=True)
                (destination / 'investigation.json').write_text(json.dumps({
                    'status': 'completed', 'claims': [{'id': 'a', 'root_cause': 'same', 'status': 'verified', 'evidence_ref': 'proof.json'},
                                                       {'id': 'b', 'root_cause': 'unknown', 'status': 'unresolved', 'evidence_ref': None}],
                    'resources': {'elapsed_seconds': 1}, 'agent': {'elapsed_seconds': .5}}))
        report = self.report()
        self.assertEqual(len(report['supplementary']['verified_root_causes']), 2)
        self.assertEqual(report['supplementary']['claims']['unresolved'], 4)
        self.assertIn('dependent', ' '.join(report['limitations']))
        self.assertIn('unknown', self.cli('report', '--format', 'markdown').stdout)
