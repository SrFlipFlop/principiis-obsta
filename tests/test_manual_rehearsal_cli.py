"""Development rehearsals retain checkpoints without inventing an evaluator."""
import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import fixture_runtime


ROOT = Path(__file__).resolve().parents[1]


class ManualRehearsal(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.output = self.base / 'run'
        self.sequence = self.base / 'sequence.json'
        self.agent = self.base / 'agent.py'
        self.agent.write_text(
            "from pathlib import Path\nimport sys\n"
            "old=Path('notes').read_text() if Path('notes').exists() else 'empty'\n"
            "request=sys.stdin.read()\n"
            "Path('notes').write_text(request)\n"
            "Path('prior-notes').write_text(old)\n"
            "print('actual fixture process; no model call')\n")
        self.runtime = self.base / 'runtime.json'
        self.runtime.write_text(json.dumps({'argv': [sys.executable, str(self.agent)]}))
        self.manifest = {
            'id': 'rehearsal', 'version': '1',
            'condition': {'id': 'ordinary', 'version': '1'},
            'steps': [{'id': name, 'version': '1', 'sequence_version': '1',
                       'request': name + '.txt'} for name in ('one', 'two', 'three')],
        }
        for name in ('one', 'two', 'three'):
            (self.base / (name + '.txt')).write_text(name + ' visible requirements')
        self.write_manifest()

    def write_manifest(self):
        self.sequence.write_text(json.dumps(self.manifest))

    def develop(self, step='one', retry=False, **extra):
        return fixture_runtime.develop(self.sequence, self.output, step, self.runtime, retry=retry, **extra)

    def test_unbound_rehearsal_retains_fresh_incremental_checkpoints(self):
        self.develop()
        one = self.output / 'steps/one'
        initial_bytes = (one / 'result.json').read_bytes()
        result = json.loads(initial_bytes)
        self.assertEqual(result['outcome'], 'pending_evaluation')
        self.assertEqual(result['run_mode'], 'development-rehearsal')
        self.assertEqual(result['evaluator_binding'], 'unbound')
        self.assertEqual(result['evaluation'], {})
        self.assertFalse((one / 'evaluator.stdout').exists())
        self.assertFalse((self.output / 'steps/two').exists())
        self.assertFalse((self.output / 'evaluations').exists())
        task = json.loads((self.output / 'tasks/one.json').read_text())
        self.assertNotIn('check', task)
        self.assertEqual(task['evaluator_binding'], 'unbound')
        state = json.loads((self.output / 'manual.json').read_text())
        self.assertEqual(state['run_mode'], 'development-rehearsal')
        self.develop('two')
        two = self.output / 'steps/two'
        second_result = json.loads((two / 'result.json').read_text())
        self.assertNotEqual(result['session_id'], second_result['session_id'])
        self.assertEqual(result['run_id'], second_result['run_id'])
        self.assertEqual((two / 'snapshot/prior-notes').read_text(), 'one visible requirements')
        self.assertEqual((two / 'snapshot/notes').read_text(),
                         'one visible requirements\n\ntwo visible requirements')
        self.assertEqual((one / 'result.json').read_bytes(), initial_bytes)
        with self.assertRaisesRegex(ValueError, 'next unfinished checkpoint'):
            self.develop('one')

    def test_evaluator_changes_do_not_rewrite_rehearsal_development_provenance(self):
        for step in self.manifest['steps']:
            step['check'] = [sys.executable, 'unqualified.py']
        self.write_manifest()
        self.develop()
        fingerprint = json.loads((self.output / 'manual.json').read_text())['fingerprint']
        for step in self.manifest['steps']:
            step['check'] = [sys.executable, 'different-unqualified.py']
        self.write_manifest()
        self.develop('two')
        self.assertEqual(json.loads((self.output / 'manual.json').read_text())['fingerprint'], fingerprint)
        (self.base / 'three.txt').write_text('changed request identity')
        with self.assertRaisesRegex(ValueError, 'use a new run'):
            self.develop('three')
        self.assertEqual(len(json.loads((self.output / 'manual.json').read_text())['attempts']), 2)

    def test_malformed_manifest_is_rejected_before_allocation(self):
        invalid = [
            ('condition', {'id': 'ordinary'}),
            ('condition', {'id': 'ordinary', 'version': []}),
            ('steps', []),
            ('steps', [dict(self.manifest['steps'][0], id='')]),
            ('steps', [dict(self.manifest['steps'][0], id='../escape')]),
            ('steps', [dict(self.manifest['steps'][0], request=[])]),
        ]
        original = json.loads(json.dumps(self.manifest))
        for key, value in invalid:
            with self.subTest(key=key, value=value):
                self.manifest = dict(original, **{key: value})
                self.write_manifest()
                with self.assertRaises(ValueError):
                    self.develop()
                self.assertFalse(self.output.exists())
        self.manifest = original
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'next unfinished checkpoint'):
            self.develop('two')
        self.assertFalse(self.output.exists())

    def test_invalid_runtime_is_rejected_before_any_attempt_allocation(self):
        from principiis.manual import develop
        args = SimpleNamespace(sequence=self.sequence, output=self.output, step='one',
                               runtime_config='/operator/invalid-runtime.json', retry=False)
        class InvalidRuntime:
            def __init__(self, *unused):
                raise ValueError('malformed runtime configuration')
        with patch('principiis.development_runtime.DevelopmentRuntime', InvalidRuntime):
            with self.assertRaisesRegex(ValueError, 'malformed runtime'):
                develop(args)
        self.assertFalse(self.output.exists())

    def test_launch_authorization_is_retained_without_entering_developer_context(self):
        authorization = {'record': '/operator/owner-scope.txt', 'sha256': 'a' * 64,
                         'step': 'one', 'scope': 'fixture audit control only'}
        result = self.develop(launch_authorization=authorization)
        self.assertEqual(result['launch_authorization'], authorization)
        retained = json.loads((self.output / 'steps/one/result.json').read_text())
        allocation = json.loads((self.output / 'manual.json').read_text())['attempts'][0]
        self.assertEqual(retained['launch_authorization'], authorization)
        self.assertEqual(allocation['launch_authorization'], authorization)
        self.assertEqual((self.output / 'steps/one/snapshot/notes').read_text(),
                         'one visible requirements')

    def test_missing_completed_result_does_not_reopen_checkpoint_for_retry(self):
        self.develop()
        (self.output / 'steps/one/result.json').unlink()
        with self.assertRaisesRegex(ValueError, 'completed'):
            self.develop('one', retry=True)
        self.assertFalse((self.output / 'attempts').exists())

    def test_malformed_journal_cannot_redirect_or_duplicate_attempts(self):
        self.develop()
        journal = self.output / 'manual.json'
        original = json.loads(journal.read_text())
        record = original['attempts'][0]
        bad_records = [
            [dict(record, artifact='steps/one/workspace/fake')],
            [dict(record, artifact='../outside')],
            [dict(record, artifact='/tmp/unrelated')],
            [record, record],
            [dict(record, attempt=2)],
            [dict(record, id='unknown')],
        ]
        for records in bad_records:
            with self.subTest(records=records):
                journal.write_text(json.dumps(dict(original, attempts=records)))
                with self.assertRaisesRegex(ValueError, 'journal'):
                    self.develop('two')
                self.assertFalse((self.output / 'steps/two').exists())
        journal.write_text(json.dumps(original))
        self.develop('two')
        state = json.loads(journal.read_text())
        state['attempts'].reverse()
        journal.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'journal'):
            self.develop('three')
        self.assertFalse((self.output / 'steps/three').exists())

    def test_orphan_allocation_requires_explicit_retry_with_distinct_attempt(self):
        self.develop()
        journal = self.output / 'manual.json'
        state = json.loads(journal.read_text())
        state['attempts'].append({'id': 'two', 'artifact': 'steps/two', 'attempt': 1})
        journal.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'explicit --retry'):
            self.develop('two')
        self.develop('two', retry=True)
        result = json.loads((self.output / 'attempts/two/2/result.json').read_text())
        self.assertEqual(result['attempt'], 2)
        self.assertEqual((self.output / 'attempts/two/2/snapshot/prior-notes').read_text(),
                         'one visible requirements')
        self.assertEqual(json.loads(journal.read_text())['attempts'][1], state['attempts'][1])

    def test_sigterm_retry_restores_last_completed_snapshot_and_retains_partial_evidence(self):
        self.develop()
        original = (self.output / 'steps/one/result.json').read_bytes()
        self.agent.write_text(
            "from pathlib import Path\nimport sys,time\n"
            "assert Path('notes').read_text() == 'one visible requirements'\n"
            "if len(sys.stdin.read().split('\\n\\n')) == 2:\n"
            " Path('notes').write_text('partial edits must not continue')\n"
            " Path('partial').write_text('retain')\n"
            " print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":7,\"output_tokens\":2}}',flush=True)\n"
            " time.sleep(60)\n")
        command = [sys.executable, str(Path(fixture_runtime.__file__)), str(self.sequence),
                   str(self.output), 'two', str(self.runtime)]
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            partial = self.output / 'steps/two/workspace/partial'
            deadline = time.monotonic() + 5
            while not partial.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(partial.exists())
            process.terminate()
            process.communicate(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
        incomplete = self.output / 'steps/two/result.json'
        incomplete_bytes = incomplete.read_bytes()
        first = json.loads(incomplete_bytes)
        self.assertFalse(first['completed'])
        self.assertIn('interrupted', first['execution']['error'])
        self.assertGreater(first['execution']['elapsed_seconds'], 0)
        self.assertIn('turn.completed', (incomplete.parent / 'executor.stdout').read_text())
        self.agent.write_text(
            "from pathlib import Path\nimport sys\n"
            "assert Path('notes').read_text() == 'one visible requirements'\n"
            "assert not Path('partial').exists()\n"
            "Path('notes').write_text(sys.stdin.read())\n")
        self.develop('two', retry=True)
        second = json.loads((self.output / 'attempts/two/2/result.json').read_text())
        self.assertTrue(second['completed'])
        self.assertNotEqual(first['session_id'], second['session_id'])
        self.assertEqual(incomplete.read_bytes(), incomplete_bytes)
        self.assertEqual((self.output / 'steps/one/result.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
