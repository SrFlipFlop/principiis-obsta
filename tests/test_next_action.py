"""The operator's next action is a pure function of run state."""
import unittest

from principiis.status import next_action


def checkpoint(step, *, completed=False, attempts=0, primary=False, reviews=(), auth=False):
    return {'id': step, 'completed': completed, 'attempts': attempts, 'primary': primary,
            'investigations': list(reviews), 'failure_reason': 'codex_authentication' if auth else None}


DONE = dict(completed=True, attempts=1)
ASSESSED = dict(DONE, primary=True)

# (name, checkpoints, keyword state, expected action, expected step, expected retry)
CASES = [
    ('first step of an unbound rehearsal', [checkpoint('s1'), checkpoint('s2')],
     dict(run_mode='development-rehearsal', bound=False), 'develop', 's1', False),
    ('next unfinished step', [checkpoint('s1', **DONE), checkpoint('s2')],
     dict(run_mode='development-rehearsal', bound=False), 'develop', 's2', False),
    ('failed attempt needs an explicit retry', [checkpoint('s1', attempts=1)],
     dict(run_mode='development-rehearsal', bound=False), 'retry', 's1', True),
    ('one attempt plus three retries exhausts the step', [checkpoint('s1', attempts=4)],
     dict(run_mode='development-rehearsal', bound=False), 'new-run-required', 's1', True),
    ('unbound rehearsal finishes after development', [checkpoint('s1', **DONE)],
     dict(run_mode='development-rehearsal', bound=False), 'development-complete', None, False),
    ('full sequence without an evaluator needs a new run', [checkpoint('s1')],
     dict(run_mode='qualification', bound=False), 'new-run-required', None, False),
    ('bound run evaluates before developing further', [checkpoint('s1', **DONE), checkpoint('s2')],
     dict(run_mode='qualification', bound=True), 'evaluate', 's1', False),
    ('bound run develops once the step is assessed', [checkpoint('s1', **ASSESSED), checkpoint('s2')],
     dict(run_mode='qualification', bound=True), 'develop', 's2', False),
    ('bound run completes', [checkpoint('s1', **ASSESSED)],
     dict(run_mode='qualification', bound=True), 'development-complete', None, False),
    ('final review after every primary assessment', [checkpoint('s1', **ASSESSED), checkpoint('s2', **ASSESSED)],
     dict(run_mode='qualification', bound=True, investigation='final'), 'evaluate --final --ai-review', 's2', False),
    ('failed final review is rerun', [checkpoint('s1', **ASSESSED, reviews=['agent_error'])],
     dict(run_mode='qualification', bound=True, investigation='final'), 'evaluate --final --ai-review', 's1', True),
    ('completed final review finishes', [checkpoint('s1', **ASSESSED, reviews=['completed'])],
     dict(run_mode='qualification', bound=True, investigation='final'), 'development-complete', None, False),
    ('final review waits for the last assessment', [checkpoint('s1', **ASSESSED), checkpoint('s2', **DONE)],
     dict(run_mode='qualification', bound=True, investigation='final'), 'evaluate', 's2', False),
    ('each-step review precedes further development', [checkpoint('s1', **ASSESSED), checkpoint('s2')],
     dict(run_mode='qualification', bound=True, investigation='each-step'), 'evaluate --ai-review', 's1', False),
    ('each-step review rerun after a failed review', [checkpoint('s1', **ASSESSED, reviews=['agent_error'])],
     dict(run_mode='qualification', bound=True, investigation='each-step'), 'evaluate --ai-review', 's1', True),
    ('each-step review rerun that completed lets development continue',
     [checkpoint('s1', **ASSESSED, reviews=['agent_error', 'completed']), checkpoint('s2')],
     dict(run_mode='qualification', bound=True, investigation='each-step'), 'develop', 's2', False),
    ('final review rerun that completed finishes',
     [checkpoint('s1', **ASSESSED, reviews=['agent_error', 'completed'])],
     dict(run_mode='qualification', bound=True, investigation='final'), 'development-complete', None, False),
    ('runtime cleanup blocks development', [checkpoint('s1', **DONE), checkpoint('s2')],
     dict(run_mode='development-rehearsal', bound=False, cleanup={'cleanup': 's1'}), 'cleanup', 's1', False),
    ('evaluation cleanup outranks runtime cleanup', [checkpoint('s1', **DONE)],
     dict(run_mode='qualification', bound=True, cleanup={'cleanup': 's1', 'cleanup-evaluation': 's1'}),
     'cleanup-evaluation', 's1', False),
    ('cleanups outrank the final review', [checkpoint('s1', **ASSESSED)],
     dict(run_mode='qualification', bound=True, investigation='final', cleanup={'cleanup': 's1'}), 'cleanup', 's1', False),
    ('reviewer cleanup outranks every other cleanup', [checkpoint('s1', **ASSESSED)],
     dict(run_mode='qualification', bound=True, cleanup={'cleanup': 's1', 'cleanup-investigation': 's1'}),
     'cleanup-investigation', 's1', False),
    ('an active operation means wait', [checkpoint('s1')],
     dict(run_mode='development-rehearsal', bound=False, active=True, cleanup={'cleanup-investigation': 's1'}),
     'wait', None, False),
]


class NextAction(unittest.TestCase):
    def test_cases(self):
        for name, checkpoints, state, action, step, retry in CASES:
            with self.subTest(name):
                result = next_action(checkpoints, **state)
                self.assertEqual((result['action'], result['step'], result['retry']), (action, step, retry))
                self.assertTrue(result['explanation'])

    def test_authentication_failure_explains_how_to_retry(self):
        result = next_action([checkpoint('s1', attempts=1, auth=True)], run_mode='development-rehearsal', bound=False)
        self.assertEqual(result['action'], 'retry')
        self.assertIn('Refresh the private auth file', result['explanation'])


if __name__ == '__main__':
    unittest.main()
