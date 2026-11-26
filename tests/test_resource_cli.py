import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResourcesCLI(unittest.TestCase):
    def test_inspection_counts_attempts_once_and_preserves_unknowns(self):
        with temporary_directory() as directory:
            root = Path(directory)
            for name, session, outcome in [('failed', 'a', 'incomplete'), ('retry', 'b', 'joint_pass'), ('copy', 'b', 'joint_pass')]:
                attempt = root / name
                attempt.mkdir()
                result = {'run_id': 'run', 'session_id': session, 'checkpoint': 'one', 'attempt': 1,
                          'outcome': outcome, 'execution': {'elapsed_seconds': 4, 'started_at': 10, 'finished_at': 14},
                          'evaluation': {'elapsed_seconds': 2, 'started_at': 13, 'finished_at': 15} if session == 'b' else {}}
                (attempt / 'result.json').write_text(json.dumps(result))
                (attempt / 'executor.stdout').write_text('\n'.join(json.dumps(event) for event in [
                    {'type': 'turn.completed', 'id': 'turn-1', 'usage': {'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 20, 'reasoning_output_tokens': 5}},
                    {'type': 'turn.completed', 'id': 'turn-1', 'usage': {'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 20, 'reasoning_output_tokens': 5}},
                    {'type': 'item.completed', 'usage': {'input_tokens': 900}},
                ]))
            completed = subprocess.run([sys.executable, '-m', 'principiis.resource', str(root)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(len(report['attempts']), 2)
            self.assertEqual(report['totals']['development']['tokens'], {'input_tokens': 200, 'cached_input_tokens': 80, 'output_tokens': 40, 'reasoning_output_tokens': 10, 'total_tokens': 240})
            self.assertEqual(report['totals']['stage_duration_seconds'], 10)
            self.assertEqual(report['totals']['wall_elapsed_seconds'], 5)
            self.assertIsNone(report['totals']['evaluation']['tokens'])
            self.assertIsNone(report['actual_spending'])
            self.assertIsNone(report['api_equivalent_estimate'])
            self.assertIn('incomplete', [attempt['outcome'] for attempt in report['attempts']])

    def test_process_measurements_use_clock_and_interrupted_children_are_stopped(self):
        from principiis.resource import execute
        from io import StringIO
        import os
        import signal
        import threading
        import time
        with temporary_directory() as directory:
            root = Path(directory)
            ticks = iter([10.0, 13.5])
            dates = iter([100.0, 103.5])
            stdout, stderr = StringIO(), StringIO()
            evidence = execute([sys.executable, '-c', 'print("fixture")'], root, '', stdout, stderr,
                               clock=lambda: next(ticks), wall_clock=lambda: next(dates))
            self.assertEqual(evidence['elapsed_seconds'], 3.5)
            self.assertEqual((evidence['started_at'], evidence['finished_at']), (100.0, 103.5))
            self.assertEqual(stdout.getvalue(), 'fixture\n')
            self.assertIn('scope', evidence['memory'])
            script = root / 'parent.py'
            script.write_text('import subprocess,sys,time,pathlib\np=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])\npathlib.Path("child.pid").write_text(str(p.pid))\ntime.sleep(60)\n')
            def interrupt():
                for _ in range(200):
                    if (root / 'child.pid').exists():
                        os.kill(os.getpid(), signal.SIGINT)
                        return
                    time.sleep(.01)
            thread = threading.Thread(target=interrupt)
            thread.start()
            evidence = execute([sys.executable, str(script)], root, '', StringIO(), StringIO())
            thread.join()
            self.assertEqual(evidence['error'], 'controller interrupted')
            pid = int((root / 'child.pid').read_text())
            status = Path('/proc') / str(pid) / 'stat'
            self.assertTrue(not status.exists() or status.read_text().split(') ')[1].startswith('Z'))

    def test_real_fixture_retains_separate_development_and_evaluation_measurements(self):
        with temporary_directory() as directory:
            output = Path(directory) / 'attempt'
            completed = subprocess.run([sys.executable, '-m', 'principiis', 'run', '--task', str(ROOT / 'fixtures/engineering/task.json'), '--executor', json.dumps([sys.executable, str(ROOT / 'fixtures/engineering/executor.py'), 'pass']), '--output', str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads((output / 'result.json').read_text())
            for stage in ('execution', 'evaluation'):
                self.assertGreater(result[stage]['elapsed_seconds'], 0)
                self.assertGreater(result[stage]['finished_at'], result[stage]['started_at'])
                self.assertIn('peak_sampled_rss_bytes', result[stage]['memory'])

    def test_missing_usage_and_duration_do_not_disappear_from_totals(self):
        with temporary_directory() as directory:
            root = Path(directory)
            for session in ('known', 'unknown'):
                attempt = root / session
                attempt.mkdir()
                result = {'run_id': 'run', 'session_id': session, 'checkpoint': session, 'attempt': 1,
                          'outcome': 'incomplete', 'execution': {'exit_status': None}, 'evaluation': {}}
                if session == 'known':
                    result['execution']['elapsed_seconds'] = 3
                    (attempt / 'executor.stdout').write_text(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}}))
                (attempt / 'result.json').write_text(json.dumps(result))
            completed = subprocess.run([sys.executable, '-m', 'principiis.resource', str(root)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            totals = json.loads(completed.stdout)['totals']
            self.assertIsNone(totals['development']['tokens'])
            self.assertIsNone(totals['development']['duration_seconds'])
            self.assertIsNone(totals['stage_duration_seconds'])

    def test_readable_report_labels_unknown_cost_and_token_subsets(self):
        with temporary_directory() as directory:
            root = Path(directory)
            (root / 'result.json').write_text(json.dumps({'run_id': 'r', 'session_id': 's', 'checkpoint': 'step', 'attempt': 1, 'outcome': 'incomplete', 'execution': {'elapsed_seconds': 3}, 'evaluation': {}}))
            completed = subprocess.run([sys.executable, '-m', 'principiis.resource', str(root), '--format', 'markdown'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('step', completed.stdout)
            self.assertIn('Actual spending: unknown', completed.stdout)
            self.assertIn('Cached input is a subset', completed.stdout)

    def test_readable_report_explains_partial_token_total_after_retry(self):
        from principiis import resource
        report = resource.summarize([
            {'run_id': 'run', 'session_id': 'failed', 'checkpoint': 'step-01', 'attempt': 1,
             'outcome': 'incomplete', 'stages': {'development': {'elapsed_seconds': 7, 'tokens': None}, 'evaluation': {}}},
            {'run_id': 'run', 'session_id': 'retry', 'checkpoint': 'step-01', 'attempt': 2,
             'outcome': 'pending_evaluation', 'stages': {'development': {
                 'elapsed_seconds': 206, 'tokens': {'input_tokens': 129127, 'cached_input_tokens': 113408,
                                                   'output_tokens': 9250, 'reasoning_output_tokens': 156,
                                                   'total_tokens': 138377}}, 'evaluation': {}}},
        ])
        rendered = resource.markdown(report)
        self.assertIn('138,377 measured across 1 of 2 attempts; full total unknown', rendered)
        self.assertNotIn('development tokens: null', rendered)
        self.assertIn('## Attempt measurements', rendered)
