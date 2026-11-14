import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReviewRegressions(unittest.TestCase):
    def test_hard_killed_evaluator_retains_live_logs_without_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            check = base / 'check.py'
            check.write_text("import os,time\nfrom pathlib import Path\nPath('" + str(base / 'pid') + "').write_text(str(os.getpid()))\nprint('partial stdout',flush=True)\nprint('partial stderr',file=__import__('sys').stderr,flush=True)\ntime.sleep(60)\n")
            task = json.loads((ROOT / 'fixtures/engineering/task.json').read_text())
            task.update(request=str(ROOT / 'fixtures/engineering/request.txt'), check=[sys.executable, str(check)])
            source = base / 'task.json'
            source.write_text(json.dumps(task))
            output = base / 'run'
            process = subprocess.Popen([sys.executable, '-m', 'principiis', 'run', '--task', str(source), '--executor', json.dumps([sys.executable, str(ROOT / 'fixtures/engineering/executor.py'), 'pass']), '--output', str(output)], cwd=ROOT)
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if (base / 'pid').exists():
                        time.sleep(.15)
                        break
                    time.sleep(.02)
                process.kill()
                process.wait(timeout=5)
                self.assertEqual((output / 'evaluator.stdout').read_text(), 'partial stdout\n')
                self.assertEqual((output / 'evaluator.stderr').read_text(), 'partial stderr\n')
                result = json.loads((output / 'result.json').read_text())
                self.assertEqual((result['functional'], result['security']), ('unknown', 'unknown'))
                self.assertFalse(result['completed'])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if (base / 'pid').exists():
                    try:
                        os.killpg(int((base / 'pid').read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_resource_inspection_keeps_hard_interrupted_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for number in (1, 2):
                attempt = base / str(number)
                attempt.mkdir()
                (attempt / 'result.json').write_text(json.dumps({'run_id': 'r', 'session_id': str(number), 'checkpoint': 'one', 'attempt': number, 'outcome': 'incomplete', 'execution': {} if number == 1 else {'elapsed_seconds': 2}, 'evaluation': {}}))
                (attempt / 'executor.stdout').write_text(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}}))
            result = subprocess.run([sys.executable, '-m', 'principiis.resource', str(base)], cwd=ROOT, capture_output=True, text=True, check=True)
            report = json.loads(result.stdout)
            self.assertEqual(report['totals']['development']['attempts_present'], 2)
            self.assertEqual(report['totals']['development']['tokens']['total_tokens'], 30)
            self.assertIsNone(report['totals']['development']['duration_seconds'])
            self.assertIsNone(report['attempts'][0]['stages']['development'].get('memory'))

    def test_checkpoint_rejects_absolute_workspace_links_without_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            executor = base / 'executor.py'
            executor.write_text("from pathlib import Path\nPath('target').write_text('original')\nPath('link').symlink_to(Path('target').resolve())\n")
            output = base / 'run'
            subprocess.run([sys.executable, '-m', 'principiis', 'run', '--task', str(ROOT / 'fixtures/engineering/task.json'), '--executor', json.dumps([sys.executable, str(executor)]), '--output', str(output)], cwd=ROOT, check=True)
            result = json.loads((output / 'result.json').read_text())
            self.assertEqual(result['outcome'], 'incomplete')
            self.assertIn('symlink', result['snapshot_error'])
            self.assertFalse((output / 'snapshot').exists())
            self.assertFalse((output / 'evaluator.stdout').exists())
            self.assertEqual(result['functional'], 'unknown')

    def test_internal_relative_links_are_isolated_and_corruption_blocks_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'one.txt').write_text('one')
            (base / 'two.txt').write_text('two')
            (base / 'executor.py').write_text("from pathlib import Path\nimport sys\nif sys.stdin.read() == 'one':\n Path('target').write_text('original')\n Path('link').symlink_to('target')\nelse: sys.exit(7)\n")
            (base / 'check.py').write_text("from pathlib import Path\nassert Path('link').read_text() == 'original'\nPath('link').write_text('evaluation mutation')\nprint('{\"functional\":\"pass\",\"security\":\"pass\"}')\n")
            manifest = {'id': 's', 'version': '1', 'condition': {'id': 'ordinary', 'version': '1'}, 'steps': [{'id': key, 'version': '1', 'sequence_version': '1', 'request': key + '.txt', 'check': [sys.executable, 'check.py']} for key in ('one', 'two')]}
            source = base / 'sequence.json'
            source.write_text(json.dumps(manifest))
            output = base / 'run'
            argv = [sys.executable, '-m', 'principiis', 'sequence', '--sequence', str(source), '--executor', json.dumps([sys.executable, str(base / 'executor.py')]), '--output', str(output)]
            subprocess.run(argv, cwd=ROOT, check=True)
            snapshot = output / 'steps/one/snapshot'
            self.assertTrue((snapshot / 'link').is_symlink())
            (output / 'steps/one/workspace/target').write_text('workspace mutation')
            self.assertEqual((snapshot / 'link').read_text(), 'original')
            (snapshot / 'target').write_text('corrupted')
            resumed = subprocess.run(argv + ['--resume', '--retry-incomplete'], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(resumed.returncode, 0)
            self.assertIn('snapshot integrity', resumed.stderr)
            self.assertFalse((output / 'attempts/two/2').exists())

    def test_rescore_rejects_modified_retained_snapshot_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / 'run'
            subprocess.run([sys.executable, '-m', 'principiis', 'run', '--task', str(ROOT / 'fixtures/engineering/task.json'), '--executor', json.dumps([sys.executable, str(ROOT / 'fixtures/engineering/executor.py'), 'pass']), '--output', str(output)], cwd=ROOT, check=True)
            (output / 'snapshot/answer.txt').write_text('tampered')
            report = base / 'rescore'
            subprocess.run([sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(output / 'snapshot'), '--output', str(report), '--app-image', 'sha256:fixture', '--evaluator-image', 'sha256:fixture', '--docker', str(base / 'must-not-launch')], cwd=ROOT, capture_output=True, text=True)
            result = json.loads((report / 'assessment.json').read_text())
            self.assertIn('snapshot integrity', result['error'])
            self.assertTrue(all(command[1] == 'rm' for command in result['commands']))
