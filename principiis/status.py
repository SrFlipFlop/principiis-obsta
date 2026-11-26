"""Run status: what a run holds and the operator's next action.

`next_action` is a pure function of run state. `build` gathers that state from a
`RunStore` once and returns the status/report dictionary the CLI prints.
"""
import json
from pathlib import Path

from . import resource
from .run_store import MAX_ATTEMPTS, digest

WAIT = {'action': 'wait', 'step': None, 'retry': False,
        'explanation': 'An operator action is active. Retained measurements may still be partial.'}
CLEANUP = {
    'cleanup': 'Retained runtime cleanup is unresolved. Run the explicit cleanup command before further development.',
    'cleanup-evaluation': 'Evaluation runtime cleanup is unresolved; explicitly clean it before development or evaluation.',
    'cleanup-investigation': 'Remove the retained reviewer container before further work.',
}


def _action(action, step=None, explanation='', retry=False):
    return {'action': action, 'step': step, 'retry': retry, 'explanation': explanation}


def next_action(checkpoints, *, run_mode, bound, investigation='none', cleanup=None, active=False):
    """The single next operator action.

    checkpoints: in sequence order, each {'id', 'completed', 'attempts' (count),
    'failure_reason', 'primary' (bool), 'investigations' (statuses, oldest first)}.
    cleanup: {'cleanup' | 'cleanup-evaluation' | 'cleanup-investigation': step}
    for each kind of unresolved runtime, in that priority order.
    """
    cleanup = cleanup or {}
    if active:
        return dict(WAIT)
    if cleanup.get('cleanup-investigation'):
        return _action('cleanup-investigation', cleanup['cleanup-investigation'], CLEANUP['cleanup-investigation'])
    for kind in ('cleanup-evaluation', 'cleanup'):
        if cleanup.get(kind):
            return _action(kind, cleanup[kind], CLEANUP[kind])
    action = _development(checkpoints)
    if run_mode == 'qualification' and not bound:
        action = _action('new-run-required', explanation='A full-sequence run needs its qualified evaluator bound during init; create a new run.')
    elif bound:
        pending = next((c for c in checkpoints if c['completed'] and not c['primary']), None)
        if pending:
            action = _action('evaluate', pending['id'], 'Run the hidden checks against the retained snapshot.')
        elif action['action'] == 'development-complete':
            action['explanation'] = 'All frozen checkpoints and primary assessments retained. Owner acceptance remains separate.'
    return _review(checkpoints, investigation) or action


def _development(checkpoints):
    pending = next((c for c in checkpoints if not c['completed']), None)
    if pending is None:
        return _action('development-complete', explanation='All frozen requests retained. Preview/report remain available; evaluator is unbound.')
    if pending['attempts'] >= MAX_ATTEMPTS:
        return _action('new-run-required', pending['id'], 'Three additional retries exhausted; retain this run.', retry=True)
    explanation = 'Run the selected development command with the reviewed runtime.'
    if pending['failure_reason'] == 'codex_authentication':
        explanation = ('Codex authentication failed. Refresh the private auth file, then '
                       'retry this step with --retry; the original attempt stays saved.')
    retry = bool(pending['attempts'])
    return _action('retry' if retry else 'develop', pending['id'], explanation, retry=retry)


def _review(checkpoints, mode):
    """The separate AI security review, when the frozen run enables it."""
    unreviewed = lambda c: not c['investigations'] or c['investigations'][0] != 'completed'
    if mode == 'each-step':
        pending = next((c for c in checkpoints if c['primary'] and unreviewed(c)), None)
        command, text = 'evaluate --ai-review', 'Run the separate security investigation for this assessed checkpoint.'
    elif mode == 'final' and checkpoints and all(c['primary'] for c in checkpoints) and unreviewed(checkpoints[-1]):
        pending = checkpoints[-1]
        command, text = 'evaluate --final --ai-review', 'Run the separate final Codex security investigation.'
    else:
        return None
    if pending is None:
        return None
    retry = bool(pending['investigations'])
    return _action(command, pending['id'], text + (' Use --rerun to retain the failed attempt.' if retry else ''), retry)


def authentication_failure(stdout_path):
    """Classify a known Codex login failure without exposing agent output."""
    if not stdout_path.is_file() or stdout_path.is_symlink():
        return False
    with stdout_path.open(errors='replace') as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            error = event.get('error') if isinstance(event, dict) and event.get('type') == 'turn.failed' else None
            message = error.get('message', '') if isinstance(error, dict) else ''
            if isinstance(message, str) and ('refresh token was already used' in message or 'token_expired' in message):
                return True
    return False


def _pending_cleanups(store, allocations, receipts):
    """Runtime allocations neither removed nor reconciled by a cleanup receipt."""
    pending = []
    for step, path in allocations:
        allocation = store.runtime_allocation(path)
        if allocation is None or allocation.get('state') == 'removed':
            continue
        if any(receipt.get('outcome') == 'removed' and receipt.get('allocation') == str(path)
               and receipt.get('allocation_sha256') == digest(path) for receipt in receipts):
            continue
        pending.append({'step': step, 'allocation': str(path), 'state': allocation.get('state'),
                        'container': allocation.get('container'), 'cleanup_argv': allocation.get('cleanup_argv')})
    return pending


def build(store):
    from .evaluation_cleanup import pending as evaluation_pending
    active = store.active_operation()
    results = [attempt.directory / 'result.json' for attempt in store.attempts if attempt.result is not None]
    measured = {entry['artifact']: entry for entry in resource.inspect(store.development, result_paths=results)['attempts']}
    ordered = [measured[str(attempt.directory / 'result.json')] if attempt.result is not None else {
        'run_id': store.run_id, 'session_id': None, 'checkpoint': attempt.step, 'attempt': attempt.number,
        'outcome': 'interrupted_allocation', 'artifact': str(attempt.directory / 'result.json'),
        'stages': {'development': {'tokens': resource.token_usage(attempt.directory / 'executor.stdout')},
                   'evaluation': {}}} for attempt in store.attempts]
    assessments = store.assessments
    evaluation_attempts = [{'run_id': a['run_id'], 'session_id': a['session_id'], 'checkpoint': a['checkpoint'],
                            'attempt': a['attempt'], 'outcome': a['outcome'], 'artifact': a['artifact'],
                            'stages': {'development': {}, 'evaluation': dict(a['evaluation'], tokens=None)}}
                           for a in assessments]
    resources = resource.summarize(ordered + evaluation_attempts)
    evaluation_cleanup = evaluation_pending(store.root, assessments) if store.binding else []
    cleanups = store.records('runtime-cleanups')
    runtime_cleanup = _pending_cleanups(store, [(a.step, a.directory / 'runtime.json') for a in store.attempts], cleanups)
    investigations = store.investigations()
    investigation_cleanups = store.records('investigation-cleanups')
    investigation_cleanup = [{'step': entry['step'], 'allocation': entry['allocation'], 'container': entry['container']}
                             for entry in _pending_cleanups(store, [(i['checkpoint'], Path(i['artifact']).parent / 'runtime.json')
                                                                     for i in investigations], investigation_cleanups)]
    checkpoints = []
    for step in store.step_ids:
        attempts = store.attempts_for(step)
        latest = attempts[-1] if attempts else None
        complete = bool(latest and latest.completed)
        directory = latest.directory if latest else None
        status = latest.result['outcome'] if latest and latest.result else 'interrupted_allocation' if latest else 'not-started'
        step_assessments = [a for a in assessments if a['checkpoint'] == step]
        checkpoints.append({
            'id': step, 'status': status, 'completed': complete, 'attempts': len(attempts),
            'source': str(directory / ('snapshot' if complete else 'workspace')) if directory else None,
            'result': str(directory / 'result.json') if directory else None,
            'stdout': str(directory / 'executor.stdout') if directory else None,
            'stderr': str(directory / 'executor.stderr') if directory else None,
            'snapshot_manifest_sha256': digest(directory / 'snapshot.json')
            if complete and (directory / 'snapshot.json').is_file() else None,
            'failure_reason': 'codex_authentication' if directory and not complete
            and authentication_failure(directory / 'executor.stdout') else None,
            'assessments': step_assessments,
            'primary_assessment': next((a for a in step_assessments if a['role'] == 'primary'), None),
            'investigations': [i for i in investigations if i['checkpoint'] == step]})
    configuration = store.configuration
    action = next_action(
        [{'id': c['id'], 'completed': c['completed'], 'attempts': c['attempts'], 'failure_reason': c['failure_reason'],
          'primary': bool(c['primary_assessment']), 'investigations': [i['status'] for i in c['investigations']]}
         for c in checkpoints],
        run_mode=configuration['run_mode'], bound=bool(store.binding),
        investigation=configuration.get('investigation', 'none'), active=active['active'],
        cleanup={'cleanup': runtime_cleanup[0]['step'] if runtime_cleanup else None,
                 'cleanup-evaluation': evaluation_cleanup[0]['checkpoint'] if evaluation_cleanup else None,
                 'cleanup-investigation': investigation_cleanup[0]['step'] if investigation_cleanup else None})
    return dict(configuration, root=str(store.root), run_id=store.run_id, checkpoints=checkpoints,
                next_action=action, resources=resources, previews=store.records('previews'), active_operation=active,
                assessment_binding=store.binding, assessments=assessments, investigations=investigations,
                evaluation_cleanup_required=evaluation_cleanup,
                runtime_cleanup_required=runtime_cleanup, runtime_cleanups=cleanups,
                investigation_cleanup_required=investigation_cleanup,
                investigation_cleanups=investigation_cleanups)
