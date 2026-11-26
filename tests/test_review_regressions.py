import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReviewRegressions(unittest.TestCase):
    def test_resource_inspection_keeps_hard_interrupted_usage(self):
        with temporary_directory() as directory:
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

