"""AI security review runs only in the isolated reviewer runtime; no host commands."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import unittest

from test_development_runtime import IMAGE, docker_fixture

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = "    pathlib.Path(workspace,'app.py').write_text(sys.stdin.read())\n"


class InvestigationCLI(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.snapshot = self.base / 'snapshot'
        self.snapshot.mkdir()
        (self.snapshot / 'app.py').write_text('print(42)')
        self.primary = self.base / 'primary.json'
        self.primary.write_text('{"functional":"pass","security":"pass"}')
        self.prompt = self.base / 'prompt.txt'
        self.prompt.write_text('Investigate fixture')
        self.output = self.base / 'output'

    def reviewer_runtime(self, response):
        docker = docker_fixture(self.base)
        source = docker.read_text()
        self.assertIn(LAUNCH, source)
        message = json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': response}})
        docker.write_text(source.replace(LAUNCH,
            "    assert 'Investigate fixture' in sys.stdin.read()\n"
            f"    print({message!r})\n"))
        auth = self.base / 'reviewer-auth.json'
        auth.write_text('opaque-test-auth-not-read-by-controller')
        runtime = self.base / 'reviewer-runtime.json'
        runtime.write_text(json.dumps({'version': '1', 'docker': str(docker), 'image': IMAGE,
                                       'auth_file': str(auth), 'clean_runtime_review': 'fixture review'}))
        return runtime

    def investigate(self, config):
        path = self.base / 'config.json'
        path.write_text(json.dumps(config))
        return subprocess.run([sys.executable, '-m', 'principiis.investigation', '--snapshot', str(self.snapshot),
                               '--primary', str(self.primary), '--config', str(path), '--prompt', str(self.prompt),
                               '--prompt-version', '1', '--output', str(self.output)],
                              cwd=ROOT, capture_output=True, text=True)

    def test_isolated_reviewer_claims_are_retained_unresolved_and_primary_unchanged(self):
        original = hashlib.sha256(self.primary.read_bytes()).hexdigest()
        runtime = self.reviewer_runtime('{"claims":[{"id":"one","root_cause":"fixture"}]}')
        result = self.investigate({'version': '1', 'model': 'default', 'settings': {},
                                   'runtime_config': str(runtime), 'timeout_seconds': None, 'evidence': {}})
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.output / 'investigation.json').read_text())
        self.assertEqual(report['status'], 'completed', report.get('error'))
        self.assertEqual([(c['id'], c['status']) for c in report['claims']], [('one', 'unresolved')])
        self.assertEqual(report['verified_root_causes'], [])
        self.assertEqual(report['tools'], [])
        self.assertTrue(report['primary']['unchanged'])
        self.assertEqual(hashlib.sha256(self.primary.read_bytes()).hexdigest(), original)
        self.assertIn('agent_message', (self.output / 'agent.stdout').read_text())

    def test_host_agent_codex_and_proof_commands_are_rejected_before_output(self):
        runtime = self.reviewer_runtime('{"claims":[]}')
        base = {'version': '1', 'model': 'default', 'settings': {}, 'timeout_seconds': None, 'evidence': {}}
        for config in (dict(base, agent=[sys.executable, '-c', 'print(1)']),
                       dict(base, codex_config=str(self.base / 'codex.json')),
                       dict(base, runtime_config=str(runtime),
                            evidence={'x': {'root_cause': 'r', 'scope': 's', 'argv': ['true']}})):
            with self.subTest(config=sorted(config)):
                self.output = self.base / ('output-' + '-'.join(sorted(config)))
                result = self.investigate(config)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse(self.output.exists())

    def test_rejected_rerun_does_not_freeze_the_reviewer_configuration(self):
        from principiis.investigation import review_checkpoint
        from support import create_run
        developer_auth = self.base / 'developer-auth.json'
        developer_auth.write_text('opaque')
        runtime = json.loads(self.reviewer_runtime('{}').read_text())
        store = create_run(self.base / 'run', runtime=dict(runtime, auth_file=str(developer_auth)))
        checkpoint = {'id': 'step-01', 'completed': True, 'primary_assessment': {'artifact': str(self.primary)},
                      'investigations': [], 'source': str(self.snapshot)}
        for version in ('1', '2'):
            config = self.base / f'config-{version}.json'
            config.write_text(json.dumps({'version': version, 'runtime_config': str(self.base / 'reviewer-runtime.json'),
                                          'evidence': {}}))
            with self.subTest(version), self.assertRaisesRegex(ValueError, 'no investigation to rerun'):
                review_checkpoint(store, checkpoint, mode='each-step', config=config, prompt=self.prompt,
                                  prompt_version='1', rerun=True)


if __name__ == '__main__':
    unittest.main()
