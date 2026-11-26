"""The run store owns the run layout; only these tests read its JSON records directly."""
import json
from pathlib import Path
import unittest

from support import temporary_directory
from principiis.run_store import RunStore
from principiis.snapshot import preserve


SEQUENCE = {'id': 'fixture-app', 'version': '1', 'condition': {'id': 'baseline', 'version': '1'},
            'steps': [{'id': f'step-0{n}', 'version': '1', 'sequence_version': '1', 'request': f'requests/0{n}.txt'}
                      for n in (1, 2, 3)]}


def create(root, **configuration):
    inputs = {'sequence.json': json.dumps(SEQUENCE).encode(), 'runtime.json': b'{"image": "fixture"}',
              **{f'requests/0{n}.txt': f'request {n}'.encode() for n in (1, 2, 3)}}
    return RunStore.create(root, dict({'run_name': root.name, 'run_mode': 'development-rehearsal'}, **configuration),
                           inputs)


def develop(store, step, *, completed=True):
    attempt = store.allocate_attempt(step)
    (attempt.directory / 'workspace').mkdir(parents=True)
    (attempt.directory / 'workspace/app.py').write_text(f'# {step} {attempt.number}\n')
    if completed:
        preserve(attempt.directory / 'workspace', attempt.snapshot)
    store.save_attempt(attempt, {
        'run_id': store.run_id, 'session_id': f'{step}-{attempt.number}', 'checkpoint': step,
        'attempt': attempt.number, 'task': {'id': step, 'version': '1'}, 'condition': SEQUENCE['condition'],
        'outcome': 'pending_evaluation' if completed else 'incomplete', 'functional': 'unknown',
        'security': 'unknown', 'completed': completed}, final=True)
    return attempt


class RunStoreTest(unittest.TestCase):
    def setUp(self):
        directory = temporary_directory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / 'run'
        self.journal = self.root / 'development/manual.json'

    def test_create_writes_one_freeze_manifest_with_controller_commit(self):
        store = create(self.root)
        configuration = json.loads((self.root / 'configuration.json').read_text())
        self.assertEqual(set(configuration['frozen_files']),
                         {'sequence.json', 'runtime.json', 'requests/01.txt', 'requests/02.txt', 'requests/03.txt'})
        self.assertIn('commit', configuration['controller'])
        self.assertEqual(store.step_ids, ['step-01', 'step-02', 'step-03'])
        self.assertIsNone(store.run_id)
        self.assertFalse((self.root / 'development').exists())
        self.assertEqual(store.request_text(1), 'request 1\n\nrequest 2')

    def test_open_rejects_changed_frozen_input_and_wrong_run_name(self):
        create(self.root)
        with self.assertRaisesRegex(ValueError, 'run identity'):
            RunStore.open(self.root, run_name='other')
        (self.root / 'requests/02.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'use a new run'):
            RunStore.open(self.root)

    def test_attempts_are_journaled_before_results_and_survive_reopen(self):
        store = create(self.root)
        develop(store, 'step-01')
        interrupted = store.allocate_attempt('step-02')
        reopened = RunStore.open(self.root)
        self.assertEqual([(a.step, a.number, a.completed) for a in reopened.attempts],
                         [('step-01', 1, True), ('step-02', 1, False)])
        self.assertIsNone(reopened.attempts[1].result)
        self.assertEqual(reopened.attempts[1].directory, interrupted.directory)
        self.assertEqual(reopened.completed('step-01').snapshot, self.root / 'development/steps/step-01/snapshot')
        retry = reopened.allocate_attempt('step-02')
        self.assertEqual(retry.directory, self.root / 'development/attempts/step-02/2')
        state = json.loads(self.journal.read_text())
        self.assertEqual(state['attempts'][0], {'id': 'step-01', 'artifact': 'steps/step-01', 'attempt': 1,
                                                'completed': True, 'outcome': 'pending_evaluation'})

    def test_corrupted_snapshot_fails_on_open(self):
        store = create(self.root)
        attempt = develop(store, 'step-01')
        (attempt.snapshot / 'app.py').write_text('changed retained source')
        with self.assertRaisesRegex(ValueError, 'snapshot integrity'):
            RunStore.open(self.root)

    def test_malformed_journal_cannot_redirect_or_duplicate_attempts(self):
        develop(create(self.root), 'step-01')
        original = json.loads(self.journal.read_text())
        record = original['attempts'][0]
        for records in ([dict(record, artifact='steps/step-01/workspace/fake')], [dict(record, artifact='../outside')],
                        [dict(record, artifact='/tmp/unrelated')], [record, record], [dict(record, attempt=2)],
                        [dict(record, id='unknown')], [dict(record, id='step-02', artifact='steps/step-02')]):
            with self.subTest(records=records):
                self.journal.write_text(json.dumps(dict(original, attempts=records)))
                with self.assertRaisesRegex(ValueError, 'journal'):
                    RunStore.open(self.root)

    def test_result_identity_must_match_its_journal_entry(self):
        attempt = develop(create(self.root), 'step-01')
        result = json.loads((attempt.directory / 'result.json').read_text())
        (attempt.directory / 'result.json').write_text(json.dumps(dict(result, run_id='injected')))
        with self.assertRaisesRegex(ValueError, 'result identity'):
            RunStore.open(self.root)

    def test_missing_completed_result_is_rejected(self):
        attempt = develop(create(self.root), 'step-01')
        (attempt.directory / 'result.json').unlink()
        with self.assertRaisesRegex(ValueError, 'completed checkpoint evidence missing'):
            RunStore.open(self.root)

    def test_runs_written_before_the_store_remain_readable(self):
        """Older runs carry a journal fingerprint and per-step task records; both are ignored."""
        store = create(self.root)
        develop(store, 'step-01')
        state = json.loads(self.journal.read_text())
        state.update(fingerprint='0' * 64, run_mode='development-rehearsal', evaluator_binding='unbound')
        state['attempts'][0]['launch_authorization'] = {'kind': 'manual_cli_invocation'}
        self.journal.write_text(json.dumps(state))
        (self.root / 'development/tasks').mkdir()
        (self.root / 'development/tasks/step-01.json').write_text('{"id": "step-01"}')
        configuration = json.loads((self.root / 'configuration.json').read_text())
        del configuration['controller']
        (self.root / 'configuration.json').write_text(json.dumps(configuration))
        reopened = RunStore.open(self.root)
        self.assertTrue(reopened.completed('step-01'))
        self.assertIn('development/tasks/step-01.json', reopened.development_files())
        develop(reopened, 'step-02')
        self.assertEqual(len(RunStore.open(self.root).attempts), 2)

    def test_assessment_ledger_must_point_at_the_completed_checkpoint(self):
        store = create(self.root)
        attempt = develop(store, 'step-01')
        from principiis.run_store import digest
        declaration = self.root.parent / 'declaration.json'
        declaration.write_text(json.dumps({'version': 'v', 'files': {}}))
        store.bind({'version': 'v', 'files': {}, 'declaration': {'version': 'v', 'files': {}},
                    'manifest_sha256': digest(declaration),
                    'package_sha256': digest(self.root / 'sequence.json')},
                   declaration, self.root / 'sequence.json')
        output = store.allocate_assessment({
            'stage': 'independent_evaluation', 'run_id': store.run_id, 'session_id': 'assessment-1',
            'checkpoint': 'step-01', 'attempt': 1, 'role': 'primary', 'binding_sha256': store.binding['manifest_sha256'],
            'developer_result_sha256': 'wrong', 'snapshot_manifest_sha256': 'wrong', 'snapshot': str(attempt.snapshot)})
        self.assertEqual(store.assessments_for('step-01')[0]['artifact'], str(output / 'result.json'))
        ledger = json.loads((self.root / 'development/evaluations/step-01/allocations.json').read_text())
        self.assertEqual(ledger[0]['session_id'], 'assessment-1')
        with self.assertRaisesRegex(ValueError, 'completed development'):
            RunStore.open(self.root)


if __name__ == '__main__':
    unittest.main()
