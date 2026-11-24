import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class OperatorCLI(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.runs = self.base / 'runs'
        self.auth = self.base / 'auth.json'
        self.auth.write_text('operator-owned fixture; must never be read')
        self.runtime = self.base / 'runtime.json'
        self.runtime.write_text(json.dumps({
            'version': '1', 'docker': '/usr/bin/true', 'image': 'sha256:' + 'a' * 64,
            'auth_file': str(self.auth), 'clean_runtime_review': 'fixture review, not qualified',
        }))

    def cli(self, command, *args, success=True):
        completed = subprocess.run([
            sys.executable, '-m', 'principiis', command, '--run', 'portal-test',
            '--runs-root', str(self.runs), *args,
        ], cwd=ROOT, capture_output=True, text=True)
        if success:
            self.assertEqual(completed.returncode, 0, completed.stderr)
        else:
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
        return completed

    def initialize(self):
        return self.cli('init', '--application', 'document-portal', '--runtime-config', str(self.runtime))

    def test_init_freezes_real_requests_without_models_or_dummy_evaluators(self):
        initialized = self.initialize()
        run = self.runs / 'portal-test'
        sequence = json.loads((run / 'sequence.json').read_text())
        self.assertEqual([s['id'] for s in sequence['steps']], ['step-01', 'step-02', 'step-03'])
        for number, step in enumerate(sequence['steps'], 1):
            self.assertNotIn('check', step)
            self.assertEqual((run / step['request']).read_bytes(),
                             (ROOT / f'benchmarks/document-portal/requests/{number:02}.txt').read_bytes())
        self.assertIn('unbound', initialized.stdout)
        self.assertFalse((run / 'development').exists())
        status = json.loads(self.cli('status', '--format', 'json').stdout)
        self.assertEqual(status['next_action']['step'], 'step-01')
        self.assertIn(f'Command: principiis develop --runs-root {self.runs} --run portal-test --step 1',
                      self.cli('status').stdout)
        self.assertEqual(status['resources']['attempts'], [])
        self.assertFalse((run / 'previews').exists())
        self.cli('init', '--application', 'document-portal', '--runtime-config', str(self.runtime), success=False)

    def test_invalid_initial_configuration_leaves_no_run(self):
        config = json.loads(self.runtime.read_text())
        config['image'] = 'latest'
        self.runtime.write_text(json.dumps(config))
        self.cli('init', '--application', 'document-portal', '--runtime-config', str(self.runtime), success=False)
        self.assertFalse((self.runs / 'portal-test').exists())

    def test_invalid_mount_directory_is_rejected_during_init(self):
        self.runs = self.base / 'runs,unsupported'
        self.cli('init', '--application', 'document-portal', '--runtime-config', str(self.runtime), success=False)
        self.assertFalse(self.runs.exists())

    def test_changed_frozen_configuration_requires_new_run_before_development(self):
        self.initialize()
        run = self.runs / 'portal-test'
        runtime = run / 'runtime.json'
        runtime.write_text(runtime.read_text() + '\n')
        rejected = self.cli('develop', '--step', '1', success=False)
        self.assertIn('new run', rejected.stderr)
        self.assertFalse((run / 'development').exists())

    def retain_attempt(self, step, number, session, completed, start, duration, input_tokens):
        run = self.runs / 'portal-test'
        relative = f'steps/{step}' if number == 1 else f'attempts/{step}/{number}'
        directory = run / 'development' / relative
        directory.mkdir(parents=True)
        (directory / 'workspace').mkdir()
        result = {
            'run_id': 'fixture-run', 'session_id': session, 'checkpoint': step,
            'attempt': number, 'outcome': 'pending_evaluation' if completed else 'incomplete',
            'completed': completed, 'execution': {
                'exit_status': 0 if completed else None, 'elapsed_seconds': duration,
                'started_at': start, 'finished_at': start + duration,
                'memory': {'peak_sampled_rss_bytes': 123, 'scope': 'fixture subprocess'},
                'container_memory': {'peak_sampled_bytes': 456, 'scope': 'fixture container'},
            }, 'evaluation': {},
        }
        (directory / 'result.json').write_text(json.dumps(result))
        (directory / 'executor.stdout').write_text(json.dumps({
            'type': 'turn.completed', 'usage': {'input_tokens': input_tokens,
                                             'cached_input_tokens': 2, 'output_tokens': 3},
        }))
        (directory / 'executor.stderr').write_text('')
        if completed:
            from principiis.snapshot import preserve
            (directory / 'workspace/app.py').write_text('# retained source fixture, never executed\n')
            preserve(directory / 'workspace', directory / 'snapshot')
        journal = run / 'development/manual.json'
        state = json.loads(journal.read_text()) if journal.exists() else {'run_id': 'fixture-run', 'attempts': []}
        state['attempts'].append({'id': step, 'artifact': relative, 'attempt': number})
        journal.write_text(json.dumps(state))
        return directory

    def test_final_review_next_action_and_report_for_three_and_ten_steps(self):
        from principiis.operator import build_status, markdown
        for count in (3, 10):
            with self.subTest(steps=count):
                if (self.runs / 'portal-test').exists():
                    import shutil
                    shutil.rmtree(self.runs / 'portal-test')
                self.initialize()
                root = self.runs / 'portal-test'
                if count == 10:
                    sequence = json.loads((root / 'sequence.json').read_text())
                    sequence['steps'].extend({'id': f'step-{number:02}'} for number in range(4, 11))
                    (root / 'sequence.json').write_text(json.dumps(sequence))
                configuration = json.loads((root / 'configuration.json').read_text())
                assessments = []
                for number in range(1, count + 1):
                    step = f'step-{number:02}'
                    self.retain_attempt(step, 1, f'session-{number}', True, number * 10, 1, 2)
                    assessments.append({'checkpoint': step, 'role': 'primary', 'outcome': 'candidate_failure',
                                        'artifact': f'/fixture/{step}.json', 'attempt': 1,
                                        'functional': 'fail', 'security': 'unknown',
                                        'checks': [{'id': 'browser-library', 'status': 'fail',
                                                    'detail': 'Expected login control; saw Sign in'}]})
                evidence = {'assessments': assessments, 'binding': {'version': 'fixture'},
                            'resources': {'attempts': []}, 'cleanup_required': []}
                with patch('principiis.assessment.inspect', return_value=evidence):
                    status = build_status(root, configuration)
                self.assertEqual(status['next_action']['action'], 'evaluate --final --ai-review')
                self.assertEqual(status['next_action']['step'], f'step-{count:02}')
                self.assertIn(f'evaluate --final --ai-review step-{count:02}', markdown(status))
                self.assertIn('browser-library: fail — Expected login control; saw Sign in', markdown(status))
                investigation = root / 'investigations' / f'step-{count:02}' / '1'
                investigation.mkdir(parents=True)
                (investigation / 'investigation.json').write_text(json.dumps({
                    'status': 'completed', 'claims': [{'id': 'fixture', 'status': 'unresolved'}],
                    'verified_root_causes': [], 'resources': {'elapsed_seconds': 1, 'reported_tokens': None},
                }))
                with patch('principiis.assessment.inspect', return_value=evidence):
                    reviewed = build_status(root, configuration)
                self.assertEqual(reviewed['next_action']['action'], 'development-complete')
                self.assertIn(f'| step-{count:02} | completed | 1 | 0 |', markdown(reviewed))

    def test_reports_follow_journal_and_reconcile_retry_without_candidate_accounting(self):
        self.initialize()
        first = self.retain_attempt('step-01', 1, 'session-one', True, 100, 4, 10)
        failed = self.retain_attempt('step-02', 1, 'session-two', False, 110, 2, 20)
        retry = self.retain_attempt('step-02', 2, 'session-three', True, 120, 3, 30)
        original = {p: p.read_bytes() for directory in (first, failed, retry)
                    for p in (directory / 'result.json', directory / 'executor.stdout')}
        # A candidate may write a convincing result file; it is never an accounting record.
        (first / 'workspace/result.json').write_text(json.dumps({
            'run_id': 'injected', 'session_id': 'injected', 'checkpoint': 'bad', 'attempt': 999,
            'outcome': 'joint_pass', 'execution': {'elapsed_seconds': 999999},
        }))
        self.cli('report', '--format', 'csv')
        report_dir = self.runs / 'portal-test/reports'
        report = json.loads((report_dir / 'development.json').read_text())
        self.assertEqual(len(report['resources']['attempts']), 3)
        totals = report['resources']['totals']
        self.assertEqual(totals['development']['duration_seconds'], 9)
        self.assertEqual(totals['wall_elapsed_seconds'], 23)
        self.assertEqual(totals['development']['tokens']['total_tokens'], 69)
        self.assertIsNone(totals['development']['tokens']['reasoning_output_tokens'])
        with (report_dir / 'development.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3)
        self.assertEqual([row['session_id'] for row in rows], ['session-one', 'session-two', 'session-three'])
        self.assertEqual(rows[1]['outcome'], 'incomplete')
        self.assertEqual(sum(float(row['development_seconds']) for row in rows), 9)
        self.assertEqual(sum(int(row['total_tokens']) for row in rows), 69)
        self.assertEqual(report['next_action']['step'], 'step-03')
        self.assertIn('unknown', (report_dir / 'development.md').read_text())
        self.assertIn(str(retry / 'snapshot'), (report_dir / 'development.md').read_text())
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content)

    def test_status_groups_run_checkpoint_evidence_and_next_command(self):
        self.initialize()
        self.retain_attempt('step-01', 1, 'first', True, 100, 4, 10)
        rendered = self.cli('status').stdout
        for heading in ('## Run', '## Checkpoints', '## Logs', '## Attempt measurements', '## Next action'):
            self.assertIn(heading, rendered)
        self.assertIn(f'principiis develop --runs-root {self.runs} --run portal-test --step 2', rendered)

    def test_status_separates_development_and_evaluation_outcomes(self):
        from principiis.operator import markdown
        report = {
            'run_name': 'demo', 'run_mode': 'development-rehearsal', 'application': 'document-portal',
            'package_version': 'v1', 'condition': {'id': 'baseline'}, 'investigation': 'none',
            'evaluator_binding': 'bound', 'assessment_binding': {'version': 'release'}, 'root': '/tmp/demo',
            'checkpoints': [
                {'id': 'step-01', 'status': 'pending_evaluation', 'attempts': 1, 'source': '/tmp/source',
                 'stdout': None, 'stderr': None, 'primary_assessment': {'outcome': 'candidate_failure'}},
                {'id': 'step-02', 'status': 'pending_evaluation', 'attempts': 1, 'source': '/tmp/source2',
                 'stdout': None, 'stderr': None, 'primary_assessment': None},
            ],
            'assessments': [], 'investigations': [], 'resources': {'attempts': [], 'totals': {
                'development': {'tokens': None}, 'evaluation': {'tokens': None},
                'wall_elapsed_seconds': None, 'stage_duration_seconds': None}},
            'runtime_cleanup_required': [], 'evaluation_cleanup_required': [],
            'investigation_cleanup_required': [], 'previews': [],
            'next_action': {'action': 'evaluate', 'step': 'step-02', 'explanation': 'Run checks.'},
        }
        rendered = markdown(report)
        self.assertIn('| Development | Evaluation |', rendered)
        self.assertIn('| step-01 | finished | candidate_failure |', rendered)
        self.assertIn('| step-02 | finished | not run |', rendered)

    def test_expired_codex_login_is_reported_as_retryable_authentication_failure(self):
        self.initialize()
        attempt = self.retain_attempt('step-01', 1, 'expired-login', False, 100, 2, 0)
        (attempt / 'executor.stdout').write_text(json.dumps({
            'type': 'turn.failed',
            'error': {'message': 'Your access token could not be refreshed because your refresh token was already used.'},
        }) + '\n')
        status = json.loads(self.cli('status', '--format', 'json').stdout)
        self.assertEqual(status['checkpoints'][0]['failure_reason'], 'codex_authentication')
        self.assertEqual(status['next_action']['action'], 'retry')
        self.assertIn('Refresh the private auth file', status['next_action']['explanation'])

    def test_status_surfaces_retry_and_retains_hard_interrupted_allocation(self):
        self.initialize()
        self.retain_attempt('step-01', 1, 'first', True, 100, 1, 10)
        partial = self.retain_attempt('step-02', 1, 'partial', False, 102, 1, 20)
        (partial / 'result.json').unlink()  # Abrupt termination between allocation and initial result.
        report = json.loads(self.cli('status', '--format', 'json').stdout)
        self.assertEqual(report['next_action']['step'], 'step-02')
        self.assertTrue(report['next_action']['retry'])
        self.assertEqual(report['resources']['totals']['development']['attempts_present'], 2)
        self.assertIsNone(report['resources']['totals']['development']['duration_seconds'])
        self.assertIn('interrupted', report['checkpoints'][1]['status'])

    def test_status_rejects_journal_paths_into_candidate_files(self):
        self.initialize()
        attempt = self.retain_attempt('step-01', 1, 'first', True, 100, 1, 10)
        journal = self.runs / 'portal-test/development/manual.json'
        state = json.loads(journal.read_text())
        state['attempts'][0]['artifact'] = 'steps/step-01/workspace'
        journal.write_text(json.dumps(state))
        rejected = self.cli('status', success=False)
        self.assertIn('artifact', rejected.stderr)

    def test_status_and_report_refuse_corrupted_completed_evidence(self):
        self.initialize()
        attempt = self.retain_attempt('step-01', 1, 'first', True, 100, 1, 10)
        (attempt / 'snapshot/app.py').write_text('changed retained source')
        rejected = self.cli('status', success=False)
        self.assertIn('snapshot integrity', rejected.stderr)
        self.cli('report', success=False)
        self.assertFalse((self.runs / 'portal-test/reports').exists())

    def test_preview_cleanup_removes_every_preview_for_selected_checkpoint(self):
        from principiis.operator import preview
        from test_development_runtime import IMAGE, docker_fixture
        self.initialize()
        self.retain_attempt('step-01', 1, 'first', True, 100, 1, 10)
        docker = docker_fixture(self.base)
        config = self.base / 'preview.json'
        config.write_text(json.dumps({'version': '1', 'docker': str(docker), 'preview': {
            'image': IMAGE, 'command': ['python', 'app.py'], 'container_port': 8123,
            'host_port': 0, 'ready_path': '/ready', 'startup_timeout_seconds': 1,
        }}))
        args = SimpleNamespace(run='portal-test', runs_root=str(self.runs), step='1',
                               preview_config=str(config), stop=False)
        with patch('principiis.preview.http.client.HTTPConnection') as connection:
            connection.return_value.getresponse.return_value.status = 200
            preview(args)
            preview(args)
        args.stop = True
        report = preview(args)
        self.assertEqual(len(report['previews']), 2)
        self.assertTrue(all(entry['evidence']['resources_removed'] for entry in report['previews']))
        commands = [json.loads(line) for line in (self.base / 'commands.jsonl').read_text().splitlines()]
        expected_containers = {entry['evidence'][key] for entry in report['previews']
                               for key in ('container', 'relay_container')}
        self.assertEqual({command[2] for command in commands if command[:2] == ['rm', '-f']}, expected_containers)
        self.assertEqual(len([command for command in commands if command[:2] == ['network', 'rm']]), 2)

    def test_orphan_runtime_cleanup_preserves_original_attempt_and_unblocks_advancement(self):
        from test_development_runtime import IMAGE, docker_fixture
        from principiis.development_runtime import docker_command
        docker = docker_fixture(self.base)
        runtime = json.loads(self.runtime.read_text())
        runtime.update(docker=str(docker), image=IMAGE)
        self.runtime.write_text(json.dumps(runtime))
        self.initialize()
        attempt = self.retain_attempt('step-01', 1, 'first', True, 100, 1, 10)
        name = 'po-development-' + 'b' * 32
        allocation = attempt / 'runtime.json'
        allocation.write_text(json.dumps({'schema_version': 1, 'adapter': 'docker-development-v1',
            'image': IMAGE, 'container': name, 'state': 'allocated',
            'cleanup_argv': docker_command(str(docker), ['rm', '-f', name])}))
        original = allocation.read_bytes()
        self.assertEqual(json.loads(self.cli('status', '--format', 'json').stdout)['next_action']['action'], 'cleanup')
        self.cli('develop', '--step', '2', success=False)
        self.assertFalse((self.runs / 'portal-test/development/steps/step-02').exists())
        cleaned = json.loads(self.cli('cleanup', '--step', '1', '--format', 'json').stdout)
        self.assertEqual(cleaned['runtime_cleanup_required'], [])
        self.assertEqual(cleaned['next_action']['step'], 'step-02')
        self.assertEqual(cleaned['runtime_cleanups'][0]['outcome'], 'removed')
        self.assertEqual(allocation.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
