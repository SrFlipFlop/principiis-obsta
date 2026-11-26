"""The develop -> evaluate pipeline, driven through its interface with fake runtimes."""
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

from support import temporary_directory
import fixture_runtime
from principiis import pipeline
from principiis.run_store import RunStore, digest

IMAGE = 'sha256:' + 'a' * 64
STEPS = ('step-01', 'step-02', 'step-03')


class FakeRuntime:
    """Records each visible request and plays a scripted developer per session."""

    def __init__(self, *behaviours):
        self.behaviours = list(behaviours)
        self.requests = []

    def execute(self, workspace, request, stdout, stderr):
        self.requests.append(request)
        behaviour = self.behaviours.pop(0) if self.behaviours else 'notes'
        prior = (workspace / 'notes').read_text() if (workspace / 'notes').exists() else 'empty'
        (workspace / 'prior-notes').write_text(prior)
        stdout.write(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 3, 'output_tokens': 1}}) + '\n')
        if behaviour == 'interrupt':
            (workspace / 'partial').write_text('partial edits')
            raise KeyboardInterrupt()
        if behaviour == 'fail':
            (workspace / 'partial').write_text('partial edits')
            return {'exit_status': 17}
        (workspace / 'notes').write_text(request)
        return {'exit_status': 0, 'elapsed_seconds': 1.0}


class FakeEvaluator:
    """Writes a restricted assessment as the real container runner would."""

    def __init__(self, outcome='candidate_failure', *, removed=True, changed=None):
        self.outcome, self.removed, self.changed = outcome, removed, changed
        self.candidates = []

    def verify(self, step):
        if self.changed:
            raise ValueError('evaluator dependency content changed: ' + self.changed)

    def run(self, candidate, output, step, stdout, stderr):
        self.candidates.append(sorted(path.name for path in candidate.iterdir()))
        output.mkdir()
        (output / 'runtime-allocation.json').write_text(json.dumps({
            'containers': {'application': 'po-app-x', 'evaluator': 'po-eval-x'},
            'cleanup_argv': [['docker', 'rm', '-f', 'po-app-x']], 'resources_removed': self.removed}))
        (output / 'assessment.json').write_text(json.dumps({
            'outcome': self.outcome, 'functional': 'pass', 'security': 'fail',
            'checks': [{'id': 'denial', 'status': 'fail'}], 'elapsed_seconds': 2}))
        return {'exit_status': 0, 'elapsed_seconds': 2.5}

    def coverage(self, step):
        return {'denial': 'security'}


class CheckpointPipeline(unittest.TestCase):
    def setUp(self):
        directory = temporary_directory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.store = self.create('development-rehearsal')

    def create(self, mode, name='run'):
        sequence = {'id': 'fixture-app', 'version': '1', 'condition': {'id': 'baseline', 'version': '1'},
                    'steps': [{'id': step, 'version': '1', 'sequence_version': '1', 'request': f'requests/{n:02}.txt'}
                              for n, step in enumerate(STEPS, 1)]}
        inputs = {'sequence.json': json.dumps(sequence).encode(),
                  'runtime.json': json.dumps({'image': IMAGE}).encode(),
                  **{f'requests/{n:02}.txt': f'request {n}'.encode() for n in (1, 2, 3)}}
        return RunStore.create(self.base / name, {'run_name': name, 'run_mode': mode}, inputs)

    def bind(self, store):
        declaration = self.base / 'declaration.json'
        manifest = {'version': 'fixture-1', 'files': {}, 'runtime_image': IMAGE, 'steps': {step: {} for step in STEPS}}
        declaration.write_text(json.dumps(manifest))
        store.bind({'version': 'fixture-1', 'files': {}, 'declaration': manifest, 'manifest_sha256': digest(declaration),
                    'package_sha256': digest(declaration)},
                   declaration, declaration)

    def develop(self, step, runtime=None, retry=False, store=None):
        return pipeline.develop(store or self.store, step, retry=retry, runtime=runtime or FakeRuntime())

    def test_each_step_is_a_fresh_session_on_the_previous_snapshot_with_cumulative_requests(self):
        runtime = FakeRuntime()
        first = pipeline.develop(self.store, 'step-01', retry=False, runtime=runtime)
        second = pipeline.develop(self.store, 'step-02', retry=False, runtime=runtime)
        self.assertEqual(runtime.requests, ['request 1', 'request 1\n\nrequest 2'])
        self.assertEqual((first['outcome'], first['completed']), ('pending_evaluation', True))
        self.assertNotEqual(first['session_id'], second['session_id'])
        self.assertEqual(first['run_id'], second['run_id'])
        snapshot = self.store.completed('step-02').snapshot
        self.assertEqual((snapshot / 'prior-notes').read_text(), 'request 1')
        self.assertEqual((snapshot / 'notes').read_text(), 'request 1\n\nrequest 2')
        self.assertIn('commit', second['controller'])
        with self.assertRaisesRegex(ValueError, 'next unfinished checkpoint'):
            self.develop('step-01')
        self.assertEqual(len(RunStore.open(self.store.root).attempts), 2)

    def test_only_the_next_unfinished_step_can_be_selected(self):
        with self.assertRaisesRegex(ValueError, 'next unfinished checkpoint'):
            self.develop('step-02')
        with self.assertRaisesRegex(ValueError, 'no failed attempt'):
            self.develop('step-01', retry=True)
        self.assertEqual(self.store.attempts, [])
        self.assertFalse((self.store.root / 'development').exists())

    def test_failed_attempt_is_retained_and_retry_restarts_from_the_last_snapshot(self):
        self.develop('step-01')
        failed = self.develop('step-02', FakeRuntime('fail'))
        self.assertEqual((failed['outcome'], failed['completed']), ('incomplete', False))
        failed_dir = self.store.attempts_for('step-02')[0].directory
        self.assertTrue((failed_dir / 'workspace/partial').exists())
        with self.assertRaisesRegex(ValueError, 'explicit --retry'):
            self.develop('step-02')
        retried = self.develop('step-02', retry=True)
        retry_dir = self.store.completed('step-02').directory
        self.assertEqual(retried['attempt'], 2)
        self.assertFalse((retry_dir / 'snapshot/partial').exists())
        self.assertEqual((retry_dir / 'snapshot/prior-notes').read_text(), 'request 1')
        self.assertTrue((failed_dir / 'workspace/partial').exists())

    def test_interrupted_session_is_kept_incomplete(self):
        result = self.develop('step-01', FakeRuntime('interrupt'))
        self.assertEqual(result['execution']['error'], 'controller interrupted')
        self.assertFalse(RunStore.open(self.store.root).attempts[0].completed)

    def test_three_retries_is_the_cap(self):
        for retry in (False, True, True, True):
            self.develop('step-01', FakeRuntime('fail'), retry=retry)
        with self.assertRaisesRegex(ValueError, 'three additional retries exhausted'):
            self.develop('step-01', retry=True)
        self.assertEqual(len(self.store.attempts), 4)

    def test_qualification_run_requires_binding_and_evaluation_between_steps(self):
        store = self.create('qualification', 'full')
        with self.assertRaisesRegex(ValueError, 'qualified evaluator binding'):
            self.develop('step-01', store=store)
        self.bind(store)
        self.develop('step-01', store=store)
        with self.assertRaisesRegex(ValueError, 'separately evaluate'):
            self.develop('step-02', store=store)
        pipeline.evaluate(store, 'step-01', rerun=False, evaluator=FakeEvaluator())
        self.develop('step-02', store=store)

    def test_evaluation_scores_a_copy_and_keeps_the_snapshot_unchanged(self):
        self.develop('step-01')
        with self.assertRaisesRegex(ValueError, 'unbound'):
            pipeline.evaluate(self.store, 'step-01', rerun=False, evaluator=FakeEvaluator())
        self.bind(self.store)
        evaluator = FakeEvaluator()
        result = pipeline.evaluate(self.store, 'step-01', rerun=False, evaluator=evaluator)
        self.assertEqual((result['role'], result['outcome'], result['functional'], result['security']),
                         ('primary', 'candidate_failure', 'pass', 'fail'))
        self.assertTrue(result['snapshot_unchanged'])
        self.assertFalse(result['cleanup_pending'])
        self.assertEqual(result['coverage'], {'denial': 'security'})
        self.assertEqual(result['evaluation']['tokens'], None)
        self.assertEqual(evaluator.candidates, [['notes', 'prior-notes']])
        self.assertEqual(RunStore.open(self.store.root).assessments_for('step-01')[0]['session_id'], result['session_id'])

    def test_rerun_is_explicit_and_keeps_the_primary(self):
        self.develop('step-01')
        self.bind(self.store)
        with self.assertRaisesRegex(ValueError, 'no primary assessment to rerun'):
            pipeline.evaluate(self.store, 'step-01', rerun=True, evaluator=FakeEvaluator())
        primary = pipeline.evaluate(self.store, 'step-01', rerun=False, evaluator=FakeEvaluator())
        with self.assertRaisesRegex(ValueError, '--rerun'):
            pipeline.evaluate(self.store, 'step-01', rerun=False, evaluator=FakeEvaluator())
        rerun = pipeline.evaluate(self.store, 'step-01', rerun=True, evaluator=FakeEvaluator('joint_pass'))
        roles = [(a['role'], a['session_id']) for a in RunStore.open(self.store.root).assessments_for('step-01')]
        self.assertEqual(roles, [('primary', primary['session_id']), ('rerun', rerun['session_id'])])

    def test_unremoved_containers_make_the_assessment_unscorable(self):
        self.develop('step-01')
        self.bind(self.store)
        result = pipeline.evaluate(self.store, 'step-01', rerun=False, evaluator=FakeEvaluator('joint_pass', removed=False))
        self.assertEqual((result['outcome'], result['cleanup_pending']), ('evaluator_error', True))
        self.assertEqual(result['containers'], {'application': 'po-app-x', 'evaluator': 'po-eval-x'})

    def test_changed_evaluator_files_are_rejected_before_allocation(self):
        self.develop('step-01')
        self.bind(self.store)
        with self.assertRaisesRegex(ValueError, 'dependency content changed'):
            pipeline.evaluate(self.store, 'step-01', rerun=False, evaluator=FakeEvaluator(changed='contract.json'))
        self.assertEqual(self.store.assessments, [])

    def test_orphan_allocation_requires_explicit_retry_with_distinct_attempt(self):
        self.develop('step-01')
        self.store.allocate_attempt('step-02')  # The controller died before writing a result.
        with self.assertRaisesRegex(ValueError, 'explicit --retry'):
            self.develop('step-02', store=RunStore.open(self.store.root))
        store = RunStore.open(self.store.root)
        result = self.develop('step-02', retry=True, store=store)
        self.assertEqual(result['attempt'], 2)
        self.assertEqual((store.completed('step-02').snapshot / 'prior-notes').read_text(), 'request 1')

    def test_sigterm_retains_partial_evidence_and_retry_restarts_from_last_snapshot(self):
        self.develop('step-01')
        agent, config = self.base / 'agent.py', self.base / 'runtime-config.json'
        config.write_text(json.dumps({'argv': [sys.executable, str(agent)]}))
        agent.write_text(
            "from pathlib import Path\nimport time\n"
            "assert Path('notes').read_text() == 'request 1'\n"
            "Path('notes').write_text('partial edits must not continue')\n"
            "Path('partial').write_text('retain')\n"
            "print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":7,\"output_tokens\":2}}',flush=True)\n"
            "time.sleep(60)\n")
        process = subprocess.Popen([sys.executable, fixture_runtime.__file__, str(self.store.root), 'step-02', str(config)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            partial = self.store.root / 'development/steps/step-02/workspace/partial'
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
        store = RunStore.open(self.store.root)
        interrupted = store.attempts_for('step-02')[0]
        self.assertFalse(interrupted.completed)
        self.assertIn('interrupted', interrupted.result['execution']['error'])
        self.assertGreater(interrupted.result['execution']['elapsed_seconds'], 0)
        self.assertIn('turn.completed', (interrupted.directory / 'executor.stdout').read_text())
        retained = (interrupted.directory / 'result.json').read_bytes()
        agent.write_text("from pathlib import Path\nimport sys\n"
                         "assert Path('notes').read_text() == 'request 1'\n"
                         "assert not Path('partial').exists()\n"
                         "Path('notes').write_text(sys.stdin.read())\n")
        self.assertTrue(fixture_runtime.develop(store.root, 'step-02', config, retry=True)['completed'])
        self.assertEqual((interrupted.directory / 'result.json').read_bytes(), retained)

    def test_evaluation_requires_a_completed_checkpoint(self):
        self.bind(self.store)
        self.develop('step-01', FakeRuntime('fail'))
        with self.assertRaisesRegex(ValueError, 'completed developer checkpoint'):
            pipeline.evaluate(self.store, 'step-01', rerun=False, evaluator=FakeEvaluator())


if __name__ == '__main__':
    unittest.main()
