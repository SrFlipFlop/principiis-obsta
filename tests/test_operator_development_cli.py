"""Operator/manual/runtime integration using executable Docker regression controls."""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:' + 'b' * 64


class OperatorDevelopmentCLI(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.runs = self.base / 'runs'
        self.run = self.runs / 'portal-integration'
        self.auth = self.base / 'auth.json'
        self.auth.write_text('opaque authentication fixture; controller must not parse')
        requests = [(ROOT / f'benchmarks/document-portal/requests/{number:02}.txt').read_text()
                    for number in range(1, 4)]
        (self.base / 'expected.json').write_text(json.dumps(requests))
        docker = self.base / 'docker'
        docker.write_text(textwrap.dedent('''\
            #!/usr/bin/env python3
            import json,pathlib,sys
            base=pathlib.Path(@BASE@)
            args=sys.argv[1:]
            assert args[:2] == ['--host','unix:///var/run/docker.sock'], args
            args=args[2:]
            with (base/'docker.jsonl').open('a') as stream:
                stream.write(json.dumps(args)+'\\n')
            if args[:2] == ['image','inspect']:
                print(json.dumps([{'Id':@IMAGE@,'Config':{'Env':['PATH=/usr/bin:/bin'],'Volumes':None}}]));sys.exit()
            if args[0] == 'run' and '--version' in args:
                print('codex-cli regression-control');sys.exit()
            if args[0] == 'run' and 'po-runtime-preflight-v1' in args:
                print(json.dumps({'sandbox':'workspace-write','symlink_targets':[
                    '/usr/local/bin/python','/usr/local/bin/python3','/usr/local/bin/python3.12']}));sys.exit()
            if args[0] == 'run' and 'test -d /workspace' in args:
                mounts=[args[index+1] for index,value in enumerate(args) if value=='--mount']
                assert len(mounts) == 1 and 'dst=/workspace,readonly' in mounts[0], mounts
                workspace=pathlib.Path(mounts[0].split('src=',1)[1].split(',')[0])
                assert workspace.is_dir()
                sys.exit()
            if args[0] == 'stats':
                print('12MiB / 4GiB');sys.exit()
            if args[:2] == ['rm','-f']:
                sys.exit()
            assert args[0] == 'run' and '-i' in args, args
            mounts=[args[index+1] for index,value in enumerate(args) if value=='--mount']
            assert len(mounts) == 2, mounts
            workspace=pathlib.Path(next(value.split('src=',1)[1].split(',')[0] for value in mounts if 'dst=/workspace' in value))
            delivered=sys.stdin.read()
            expected=json.loads((base/'expected.json').read_text())
            count_path=base/'development-count'
            count=int(count_path.read_text())+1 if count_path.exists() else 1
            count_path.write_text(str(count))
            step=min(count,3)
            assert delivered == '\\n\\n'.join(expected[:step]), 'incorrect incremental disclosure'
            assert '--ephemeral' in args and '--ignore-rules' in args and '--ignore-user-config' in args
            if count == 1:
                assert list(workspace.iterdir()) == [], 'first project is not empty'
            else:
                assert (workspace/'notes').read_text() == '\\n\\n'.join(expected[:step-1]), 'prior completed notes missing'
                assert not (workspace/'partial').exists(), 'partial edits entered retry'
            # This executable is a trusted host-side fixture, so it can inspect the
            # initial attempt evidence durable before launch. It is not among the mounts.
            initial=json.loads((workspace.parent/'result.json').read_text())
            assert initial['execution'] == {} and initial['completed'] is False
            assert initial['checkpoint'] == 'step-%02d'%step
            with (base/'deliveries.jsonl').open('a') as stream:
                stream.write(json.dumps({'count':count,'request':delivered,'initial_session':initial['session_id']})+'\\n')
            event={'type':'turn.completed','id':'fixture-turn-%s'%count,
                   'usage':{'input_tokens':count*10,'cached_input_tokens':2,
                            'output_tokens':5,'reasoning_output_tokens':1}}
            print(json.dumps(event),flush=True)
            if count == 1:
                print(json.dumps(event),flush=True)  # Duplicate explicit event ID is not additive.
            if count == 3:
                (workspace/'notes').write_text('partial changes must remain only in incomplete evidence')
                (workspace/'partial').write_text('retained incomplete control')
                sys.exit(17)
            (workspace/'notes').write_text(delivered)
            (workspace/'app.py').write_text('# regression fixture source; never execute as a portal\\n')
            (workspace/'result.json').write_text(json.dumps({'run_id':'injected','session_id':'injected',
                'checkpoint':'injected','attempt':999,'outcome':'joint_pass',
                'execution':{'elapsed_seconds':999999}}))
            ''').replace('@BASE@', repr(str(self.base))).replace('@IMAGE@', repr(IMAGE)))
        docker.chmod(0o755)
        self.runtime = self.base / 'runtime.json'
        self.runtime.write_text(json.dumps({'version': '1', 'docker': str(docker), 'image': IMAGE,
                                           'auth_file': str(self.auth),
                                           'clean_runtime_review': 'executable regression fixture only'}))

    def cli(self, command, *arguments, success=True):
        args = [sys.executable, '-m', 'principiis', command, '--run', 'portal-integration',
                '--runs-root', str(self.runs)]
        if '--format' not in arguments:
            args.extend(['--format', 'json'])
        result = subprocess.run(args + list(arguments), cwd=ROOT, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertNotIn('Traceback', result.stderr)
        return result

    def initialize(self):
        return self.cli('init', '--application', 'document-portal', '--runtime-config', str(self.runtime))

    def development_count(self):
        path = self.base / 'development-count'
        return int(path.read_text()) if path.exists() else 0

    def test_develop_markdown_reports_this_action_without_full_status(self):
        self.initialize()
        output = self.cli('develop', '--step', '1', '--format', 'markdown').stdout
        self.assertIn('Development step-01: completed', output)
        self.assertIn('Evaluation: not run by this command', output)
        self.assertIn('Saved snapshot:', output)
        self.assertIn('principiis status --runs-root', output)
        self.assertNotIn('## Attempt measurements', output)

    def test_develop_continue_explicit_retry_and_exports_reconcile_actual_process_evidence(self):
        self.initialize()
        self.assertEqual(self.development_count(), 0)
        first_status = json.loads(self.cli('develop', '--step', '1').stdout)
        self.assertEqual(self.development_count(), 1)
        self.assertEqual(first_status['next_action']['step'], 'step-02')
        first = self.run / 'development/steps/step-01'
        first_result_bytes = (first / 'result.json').read_bytes()
        first_result = json.loads(first_result_bytes)
        self.assertTrue(first_result['completed'])
        self.assertEqual(first_result['evaluation'], {})
        self.assertFalse((self.run / 'development/steps/step-02').exists())

        second_status = json.loads(self.cli('develop', '--step', '2').stdout)
        self.assertEqual(self.development_count(), 2)
        self.assertEqual(second_status['next_action']['step'], 'step-03')
        second = self.run / 'development/steps/step-02'
        second_result_bytes = (second / 'result.json').read_bytes()
        second_result = json.loads(second_result_bytes)
        self.assertNotEqual(first_result['session_id'], second_result['session_id'])
        self.assertEqual(first_result['run_id'], second_result['run_id'])
        replay = self.cli('develop', '--step', '1', success=False)
        self.assertIn('next unfinished checkpoint', replay.stderr)
        self.assertEqual(self.development_count(), 2)

        incomplete_status = json.loads(self.cli('develop', '--step', '3').stdout)
        self.assertEqual(self.development_count(), 3)
        self.assertTrue(incomplete_status['next_action']['retry'])
        incomplete = self.run / 'development/steps/step-03'
        incomplete_bytes = (incomplete / 'result.json').read_bytes()
        self.assertFalse(json.loads(incomplete_bytes)['completed'])
        self.assertTrue((incomplete / 'workspace/partial').is_file())
        implicit_retry = self.cli('develop', '--step', '3', success=False)
        self.assertIn('explicit --retry', implicit_retry.stderr)
        self.assertEqual(self.development_count(), 3)

        completed_status = json.loads(self.cli('develop', '--step', '3', '--retry').stdout)
        self.assertEqual(self.development_count(), 4)
        self.assertEqual(completed_status['next_action']['action'], 'development-complete')
        retried = self.run / 'development/attempts/step-03/2'
        retried_result = json.loads((retried / 'result.json').read_text())
        self.assertTrue(retried_result['completed'])
        self.assertNotEqual(json.loads(incomplete_bytes)['session_id'], retried_result['session_id'])
        self.assertFalse((retried / 'workspace/partial').exists())
        self.assertEqual((incomplete / 'result.json').read_bytes(), incomplete_bytes)
        self.assertEqual((first / 'result.json').read_bytes(), first_result_bytes)
        self.assertEqual((second / 'result.json').read_bytes(), second_result_bytes)
        self.assertFalse((self.run / 'development/evaluations').exists())
        self.assertFalse((self.run / 'previews').exists())
        self.assertFalse(any(self.run.rglob('evaluator.stdout')))

        deliveries = [json.loads(line) for line in (self.base / 'deliveries.jsonl').read_text().splitlines()]
        self.assertEqual(len({item['initial_session'] for item in deliveries}), 4)

        report_json = json.loads(self.cli('report', '--format', 'json').stdout)
        report_csv = self.cli('report', '--format', 'csv').stdout
        rows = list(csv.DictReader(io.StringIO(report_csv)))
        report_markdown = self.cli('report', '--format', 'markdown').stdout
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(report_json['resources']['attempts']), 4)
        self.assertEqual([row['outcome'] for row in rows],
                         ['pending_evaluation', 'pending_evaluation', 'incomplete', 'pending_evaluation'])
        self.assertEqual([row['session_id'] for row in rows], [item['initial_session'] for item in deliveries])
        totals = report_json['resources']['totals']
        self.assertEqual(totals['development']['tokens'], {
            'input_tokens': 100, 'cached_input_tokens': 8, 'output_tokens': 20,
            'reasoning_output_tokens': 4, 'total_tokens': 120})
        self.assertEqual(sum(int(row['total_tokens']) for row in rows), 120)
        self.assertAlmostEqual(sum(float(row['development_seconds']) for row in rows),
                               totals['development']['duration_seconds'])
        self.assertGreaterEqual(totals['wall_elapsed_seconds'], totals['development']['duration_seconds'])
        self.assertEqual(totals['evaluation']['attempts_present'], 0)
        self.assertTrue(all(row['actual_spending'] == 'unknown' and row['hosted_model_memory'] == 'unknown'
                            for row in rows))
        self.assertIn(str(retried / 'snapshot'), report_markdown)
        self.assertIn('unknown', report_markdown)
        self.assertEqual(json.loads((self.run / 'reports/development.json').read_text()), report_json)
        self.assertEqual((self.run / 'reports/development.csv').read_text(), report_csv)
        self.assertEqual((self.run / 'reports/development.md').read_text(), report_markdown)
        self.assertEqual(self.development_count(), 4)

    def test_invalid_selection_and_removed_authorization_flag_allocate_no_attempt(self):
        self.initialize()
        for selection, extra in (('2', ()), ('4', ()), ('1', ('--retry',))):
            with self.subTest(selection=selection, extra=extra):
                self.cli('develop', '--step', selection, *extra, success=False)
                self.assertFalse((self.run / 'development').exists())
                self.assertEqual(self.development_count(), 0)
        self.cli('develop', '--step', '1', '--authorization', 'unused', success=False)
        self.assertFalse((self.run / 'development').exists())
        self.assertEqual(self.development_count(), 0)
