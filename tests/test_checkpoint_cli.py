import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CheckpointCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_fixture(self, mode='pass', executor=None, task=None):
        output = self.root / mode
        result = subprocess.run([
            sys.executable, '-m', 'principiis', 'run',
            '--task', str(task or ROOT / 'fixtures/engineering/task.json'),
            '--executor', json.dumps(executor or [sys.executable, str(ROOT / 'fixtures/engineering/executor.py'), mode]),
            '--output', str(output),
        ], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return output, json.loads((output / 'result.json').read_text())

    def test_completed_bad_candidate_is_retained(self):
        output, result = self.run_fixture('fail')
        self.assertEqual(result['outcome'], 'candidate_failure')
        self.assertEqual(result['functional'], 'fail')
        self.assertEqual((output / 'snapshot/answer.txt').read_text(), 'wrong\n')

    def test_evaluator_error_retains_snapshot_and_evidence(self):
        output, result = self.run_fixture('evaluator-error')
        self.assertEqual(result['outcome'], 'evaluator_error')
        self.assertEqual(result['functional'], 'unknown')
        self.assertTrue((output / 'snapshot/answer.txt').exists())
        self.assertIn('broken oracle', (output / 'evaluator.stderr').read_text())

    def test_incomplete_executor_keeps_partial_files_without_scoring(self):
        output, result = self.run_fixture('incomplete')
        self.assertEqual(result['outcome'], 'incomplete')
        self.assertEqual(result['execution']['exit_status'], 7)
        self.assertEqual(result['functional'], 'unknown')
        self.assertTrue((output / 'workspace/answer.txt').exists())
        self.assertFalse((output / 'snapshot').exists())
        self.assertFalse((output / 'evaluator.stdout').exists())

    def test_malformed_evaluator_output_is_an_error_not_candidate_failure(self):
        output, result = self.run_fixture('malformed')
        self.assertEqual(result['outcome'], 'evaluator_error')
        self.assertEqual(result['security'], 'unknown')
        self.assertIn('not scores', (output / 'evaluator.stdout').read_text())

    def test_executor_launch_error_is_retained_as_incomplete(self):
        output, result = self.run_fixture('launch-error', [str(self.root / 'missing-executor')])
        self.assertEqual(result['outcome'], 'incomplete')
        self.assertIsNone(result['execution']['exit_status'])
        self.assertIn('error', result['execution'])
        self.assertFalse((output / 'snapshot').exists())

    def test_evaluator_launch_error_keeps_completed_checkpoint(self):
        task = json.loads((ROOT / 'fixtures/engineering/task.json').read_text())
        task['request'] = str(ROOT / 'fixtures/engineering/request.txt')
        task['check'] = [str(self.root / 'missing-check')]
        path = self.root / 'task.json'
        path.write_text(json.dumps(task))
        output, result = self.run_fixture('check-launch-error', task=path)
        self.assertEqual(result['outcome'], 'evaluator_error')
        self.assertIsNone(result['evaluation']['exit_status'])
        self.assertTrue((output / 'snapshot/answer.txt').exists())

    def test_evaluator_mutations_do_not_change_recoverable_snapshot(self):
        check = self.root / 'check.py'
        check.write_text("from pathlib import Path\nimport json\nPath('answer.txt').write_text('changed')\nprint(json.dumps({'functional': 'pass', 'security': 'pass'}))\n")
        task = json.loads((ROOT / 'fixtures/engineering/task.json').read_text())
        task['request'] = str(ROOT / 'fixtures/engineering/request.txt')
        task['check'] = [sys.executable, str(check)]
        path = self.root / 'task.json'
        path.write_text(json.dumps(task))
        output, result = self.run_fixture(task=path)
        self.assertEqual(result['outcome'], 'joint_pass')
        self.assertEqual((output / 'snapshot/answer.txt').read_text(), 'hello\n')
        self.assertEqual((output / 'workspace/answer.txt').read_text(), 'hello\n')

    def test_request_reaches_executor_and_completed_snapshot_is_scored(self):
        output, result = self.run_fixture()
        self.assertEqual(result['outcome'], 'joint_pass')
        self.assertEqual((output / 'snapshot/answer.txt').read_text(), 'hello\n')
        self.assertIn('joint_pass', (output / 'report.md').read_text())
        self.assertEqual(result['task'], {'id': 'engineering-greeting', 'version': '1'})
        self.assertEqual(result['condition'], {'id': 'ordinary', 'version': '1'})
        self.assertTrue(result['run_id'])
        self.assertEqual(result['attempt'], 1)
        self.assertEqual(result['checkpoint'], 'engineering-greeting')


if __name__ == '__main__':
    unittest.main()
