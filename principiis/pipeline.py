"""Checkpoint pipeline: develop one step, then separately evaluate its snapshot.

Both operations take their runtime as a dependency. A development runtime has
`execute(workspace, request, stdout, stderr) -> evidence` and an optional
`snapshot_binding`; an evaluator has `verify(step)`, `run(candidate, output, step,
stdout, stderr) -> evidence` (writing `output/assessment.json`) and `coverage(step)`.
"""
import json
from pathlib import Path
import shutil
import sys
import uuid

from .candidate_dependencies import inventory as candidate_dependency_inventory
from .run_store import MAX_ATTEMPTS, controller, digest
from .snapshot import preserve, validate

OUTCOMES = ('joint_pass', 'candidate_failure', 'unassessable', 'evaluator_error')
# An assessment that cannot be scored; never counted as a pass.
UNSCORED = {'outcome': 'evaluator_error', 'functional': 'unassessable', 'security': 'unassessable'}


def check_develop(store, step, *, retry):
    """Raise unless `step` is the next development action; returns its sequence index."""
    configuration = store.configuration
    if configuration.get('run_mode') == 'evaluation-derived':
        raise ValueError('evaluation-only derived run cannot launch development')
    if configuration['run_mode'] == 'qualification':
        if not store.binding:
            raise ValueError('full-sequence qualification requires a qualified evaluator binding before development')
        if any(store.completed(other) and not store.assessments_for(other) for other in store.step_ids):
            raise ValueError('separately evaluate the previous completed checkpoint before further qualification development')
    index = next((i for i, other in enumerate(store.step_ids) if not store.completed(other)), None)
    if index is None or store.step_ids[index] != step:
        raise ValueError('select the next unfinished checkpoint')
    previous = store.attempts_for(step)
    if previous and not retry:
        raise ValueError('incomplete attempt retained; explicit --retry required')
    if not previous and retry:
        raise ValueError('no failed attempt to retry')
    if len(previous) >= MAX_ATTEMPTS:
        raise ValueError('three additional retries exhausted')
    return index


def develop(store, step, *, retry, runtime):
    """Run one fresh developer session from the prior snapshot and preserve its own."""
    index = check_develop(store, step, retry=retry)
    version = getattr(runtime, 'version', None)
    recorded = next((a.result.get('runtime_version') for a in store.attempts
                     if a.completed and a.result.get('runtime_version') is not None), None)
    if recorded is not None and version != recorded:
        raise ValueError('development runtime changed since earlier checkpoints; use a new run')
    binding = getattr(runtime, 'snapshot_binding', None)
    prior = store.completed(store.step_ids[index - 1]) if index else None
    if prior is not None:
        validate(prior.snapshot, runtime_image=binding['image'] if binding else None)
    request = store.request_text(index)
    task = store.sequence['steps'][index]
    attempt = store.allocate_attempt(step)
    attempt.directory.mkdir(parents=True, exist_ok=False)
    workspace = attempt.directory / 'workspace'
    if prior is None:
        workspace.mkdir()
    else:
        shutil.copytree(prior.snapshot, workspace, symlinks=True)
    (attempt.directory / 'request.txt').write_text(request)
    result = {
        'schema_version': 1, 'run_id': store.run_id, 'session_id': str(uuid.uuid4()),
        'sequence': {'id': store.sequence['id'], 'version': store.sequence['version']},
        'task': {'id': task['id'], 'version': task['version']}, 'condition': store.sequence['condition'],
        'attempt': attempt.number, 'checkpoint': step, 'outcome': 'incomplete', 'functional': 'unknown',
        'security': 'unknown', 'execution': {}, 'evaluation': {}, 'completed': False, 'controller': controller(),
        'runtime_version': version,
    }
    store.save_attempt(attempt, result)
    try:
        with (attempt.directory / 'executor.stdout').open('w') as stdout, \
                (attempt.directory / 'executor.stderr').open('w') as stderr:
            result['execution'] = runtime.execute(workspace, request, stdout, stderr)
    except (OSError, KeyboardInterrupt) as error:
        result['execution'] = {'exit_status': None, 'error': str(error) or 'controller interrupted'}
    if result['execution']['exit_status'] == 0:
        try:
            preserve(workspace, attempt.snapshot, runtime_binding=binding)
            result.update(outcome='pending_evaluation', completed=True)
        except (OSError, ValueError) as error:
            result['snapshot_error'] = str(error)
    store.save_attempt(attempt, result, final=True)
    return result


def evaluate(store, step, *, rerun, evaluator):
    """Run the hidden checks against a retained snapshot in the restricted evaluator."""
    binding = store.binding
    if binding is None:
        raise ValueError('evaluator is unbound; bind a qualified evaluator before evaluation')
    manifest = binding['declaration']
    if step not in manifest['steps']:
        raise ValueError('checkpoint is outside the frozen evaluator binding')
    previous = store.assessments_for(step)
    if previous and not rerun:
        raise ValueError('primary assessment retained; explicit --rerun required')
    if not previous and rerun:
        raise ValueError('no primary assessment to rerun')
    checkpoint = store.completed(step)
    if checkpoint is None:
        raise ValueError('completed developer checkpoint required')
    snapshot = checkpoint.snapshot
    validate(snapshot, runtime_image=manifest['runtime_image'])
    evaluator.verify(step)
    number = len(previous) + 1
    result = {'schema_version': 1, 'stage': 'independent_evaluation', 'run_id': store.run_id,
              'session_id': str(uuid.uuid4()), 'checkpoint': step, 'attempt': number,
              'role': 'primary' if number == 1 else 'rerun', 'binding_sha256': binding['manifest_sha256'],
              'provenance': binding, 'developer_result_sha256': digest(checkpoint.directory / 'result.json'),
              'snapshot': str(snapshot), 'snapshot_manifest_sha256': digest(snapshot.with_suffix('.json')),
              **UNSCORED, 'evaluation': {}, 'cleanup_pending': True}
    output = store.allocate_assessment(dict(result, evidence=None))
    result['evidence'] = str(output / 'restricted/assessment.json')
    launched = False
    try:
        candidate = output / 'input'
        shutil.copytree(snapshot, candidate, symlinks=True)
        shutil.copyfile(snapshot.with_suffix('.json'), candidate.with_suffix('.json'))
        validate(candidate, runtime_image=manifest['runtime_image'])
        result['candidate_dependencies'] = candidate_dependency_inventory(candidate, result['snapshot_manifest_sha256'])
        result['python_executable'] = {'path': sys.executable, 'version': sys.version}
        result['controller'] = controller()
        with (output / 'evaluator.stdout').open('w') as stdout, (output / 'evaluator.stderr').open('w') as stderr:
            launched = True
            result['evaluation'] = dict(evaluator.run(candidate, output / 'restricted', step, stdout, stderr), tokens=None)
        if result['evaluation']['exit_status'] != 0:
            raise ValueError('restricted evaluator exited unsuccessfully')
        observed = json.loads(Path(result['evidence']).read_text())
        if observed.get('outcome') not in OUTCOMES:
            raise ValueError('invalid restricted evaluator outcome')
        result.update({key: observed[key] for key in ('outcome', 'functional', 'security', 'checks', 'error',
                                                       'evidence_sha256') if key in observed})
        result['coverage'] = evaluator.coverage(step)
        result['evaluation']['runtime_elapsed_seconds'] = observed.get('elapsed_seconds')
    except (OSError, ValueError, TypeError, KeyError, KeyboardInterrupt) as error:
        result.update(UNSCORED, error=str(error) or 'controller interrupted')
    finally:
        _record_cleanup(store, result, output / 'restricted/runtime-allocation.json', launched)
        try:
            validate(snapshot, runtime_image=manifest['runtime_image'])
            if digest(checkpoint.directory / 'result.json') != result['developer_result_sha256']:
                raise ValueError('development result changed during evaluation')
            result['snapshot_unchanged'] = True
        except (OSError, ValueError) as error:
            result.update(UNSCORED, snapshot_unchanged=False, error=str(error))
        store.save_assessment(output, result)
    return result


def _record_cleanup(store, result, allocation_path, launched):
    """An assessment whose containers may remain is never scored."""
    result['runtime_launch_attempted'] = launched
    result['cleanup_pending'] = launched
    try:
        allocation = store.record(allocation_path)
        if allocation is not None:
            result.update(runtime_allocation=str(allocation_path), containers=allocation.get('containers'),
                          cleanup_argv=allocation.get('cleanup_argv'),
                          cleanup_pending=allocation.get('resources_removed') is not True)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        result['cleanup_evidence_error'] = str(error)
    if result.get('evaluation', {}).get('termination', {}).get('forced'):
        result['cleanup_pending'] = True
    if result['cleanup_pending']:
        result.update(UNSCORED)
        result.setdefault('error', 'runtime cleanup remains unresolved')
