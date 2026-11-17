import json
import signal
import subprocess
import sys
import time
import unittest

import test_operator_development_cli as integration


class OperatorLocking(unittest.TestCase):
    def test_active_development_reports_wait_and_rejects_competing_retry(self):
        fixture = integration.OperatorDevelopmentCLI()
        fixture.setUp()
        self.addCleanup(fixture.temporary.cleanup)
        fixture.initialize()
        docker = fixture.base / 'docker'
        docker.write_text(docker.read_text().replace('delivered=sys.stdin.read()',
            "import time\n(base/'blocked').touch()\nwhile (base/'hold').exists(): time.sleep(.02)\ndelivered=sys.stdin.read()"))
        (fixture.base / 'hold').touch()
        argv = [sys.executable, '-m', 'principiis', 'develop', '--run', 'portal-integration',
                '--runs-root', str(fixture.runs), '--authorization', str(fixture.authorization),
                '--step', '1', '--format', 'json']
        process = subprocess.Popen(argv, cwd=integration.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (fixture.base / 'blocked').exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((fixture.base / 'blocked').exists(), 'fixture did not reach development boundary')
            status = json.loads(fixture.cli('status').stdout)
            self.assertEqual(status['next_action']['action'], 'wait')
            self.assertTrue(status['active_operation']['active'])
            competitor = subprocess.run(argv + ['--retry'], cwd=integration.ROOT, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(competitor.returncode, 0)
            self.assertIn('active', competitor.stderr)
            journal = json.loads((fixture.run / 'development/manual.json').read_text())
            self.assertEqual(len(journal['attempts']), 1)
            (fixture.base / 'hold').unlink()
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            finished = json.loads(stdout)
            self.assertFalse(finished['active_operation']['active'])
            self.assertEqual(finished['next_action']['step'], 'step-02')
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
