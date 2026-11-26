"""Explicit single-checkpoint development in the isolated runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from .jsonio import write_json
from .snapshot import preserve, validate


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and '\0' not in value


def _attempt_artifact(step, number):
    return Path('steps') / step if number == 1 else Path('attempts') / step / str(number)


def _journal_attempts(root, state, ids=None):
    """Read only canonical controller records, preserving interrupted allocations."""
    if not isinstance(state, dict) or not _text(state.get('run_id')) or not isinstance(state.get('attempts'), list):
        raise ValueError('invalid manual journal')
    counts, completed, loaded, sessions = {}, {}, [], set()
    order = ids if ids is not None else []
    prior = None
    for record in state['attempts']:
        if not isinstance(record, dict):
            raise ValueError('invalid manual journal attempt')
        step, number = record.get('id'), record.get('attempt')
        if (not _text(step) or Path(step).name != step or step in ('.', '..')
                or not isinstance(number, int) or isinstance(number, bool)
                or number != counts.get(step, 0) + 1 or not 1 <= number <= 4):
            raise ValueError('invalid manual journal attempt identity/order')
        if ids is None and step not in order:
            order.append(step)
        if step not in order:
            raise ValueError('unknown checkpoint in manual journal')
        if prior != step:
            expected = order[0] if prior is None else order[order.index(prior) + 1] if order.index(prior) + 1 < len(order) else None
            if step != expected or (prior is not None and prior not in completed):
                raise ValueError('out-of-order checkpoint in manual journal')
        elif step in completed:
            raise ValueError('completed checkpoint has an extra attempt in manual journal')
        expected = _attempt_artifact(step, number)
        if record.get('artifact') != str(expected):
            raise ValueError('noncanonical artifact path in manual journal')
        directory = root / expected
        if directory.resolve() != directory or (directory / 'result.json').is_symlink():
            raise ValueError('symlinked artifact path in manual journal')
        result_path = directory / 'result.json'
        result = json.loads(result_path.read_text()) if result_path.exists() else None
        if result is None:
            if record.get('completed') is True or (directory / 'snapshot').exists():
                raise ValueError('completed checkpoint evidence missing from manual journal artifact')
        else:
            if (not isinstance(result, dict) or result.get('run_id') != state['run_id']
                    or result.get('checkpoint') != step or result.get('attempt') != number
                    or not _text(result.get('session_id')) or result['session_id'] in sessions):
                raise ValueError('result identity disagrees with manual journal')
            sessions.add(result['session_id'])
            if record.get('completed') is True and result.get('completed') is not True:
                raise ValueError('completed checkpoint status disagrees with manual journal')
            if result.get('completed') is True:
                validate(directory / 'snapshot')
                completed[step] = directory / 'snapshot'
        counts[step] = number
        prior = step
        loaded.append((record, directory, result))
    return loaded, completed


def _development_contract(source):
    """Validate requests before allocation; evaluators are bound separately."""
    manifest = json.loads(source.read_text())
    if not isinstance(manifest, dict):
        raise ValueError('sequence object required')
    condition = manifest.get('condition')
    if (not _text(manifest.get('id')) or not _text(manifest.get('version'))
            or not isinstance(condition, dict)
            or not _text(condition.get('id')) or not _text(condition.get('version'))):
        raise ValueError('sequence and condition identity/version required')
    steps = manifest.get('steps')
    if not isinstance(steps, list) or not steps or not all(isinstance(step, dict) for step in steps):
        raise ValueError('nonempty sequence steps required')
    ids = [step.get('id') for step in steps]
    if (any(not _text(key) or Path(key).name != key or key in ('.', '..') for key in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('unsafe or duplicate step identity')
    requests = []
    for step in steps:
        if not _text(step.get('version')) or step.get('sequence_version') != manifest['version']:
            raise ValueError('invalid step version')
        if not _text(step.get('request')):
            raise ValueError('request file path required')
        requests.append((source.parent / step['request']).read_text())
    return manifest, requests


def develop(args):
    """Run one development-only checkpoint; called by the operator `develop` command."""
    from .development_runtime import DevelopmentRuntime
    source = Path(args.sequence).resolve()
    manifest, requests = _development_contract(source)
    steps = manifest['steps']
    ids = [s['id'] for s in steps]
    if args.step not in ids:
        raise ValueError('unknown checkpoint')
    root = Path(args.output).resolve()
    executor = DevelopmentRuntime(args.runtime_config, root, source.parent)
    configuration = {'config': executor.config, 'version': executor.version}
    # Evaluator commands never enter the development fingerprint or task records.
    frozen_manifest = dict(manifest, steps=[{key: value for key, value in step.items() if key != 'check'}
                                           for step in steps])
    contract = [frozen_manifest, requests, configuration, {'run_mode': 'development-rehearsal'}]
    fingerprint = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    run_mode, binding = 'development-rehearsal', 'unbound'
    journal = root / 'manual.json'
    if journal.exists():
        state = json.loads(journal.read_text())
        if not isinstance(state, dict):
            raise ValueError('invalid manual journal')
        if state['fingerprint'] != fingerprint:
            raise ValueError('sequence or execution configuration changed; use a new run')
    else:
        if root.exists():
            raise ValueError('existing output has no manual journal; use a new run')
        state = {'run_id': str(uuid.uuid4()), 'fingerprint': fingerprint, 'attempts': [],
                 'run_mode': run_mode, 'evaluator_binding': binding}
    # A completed result survives a crash before its final journal update. An
    # allocated attempt without a result still consumes a distinct explicit retry.
    _, completed = _journal_attempts(root, state, ids)
    index = next((i for i,s in enumerate(steps) if s['id'] not in completed), None)
    if index is None or steps[index]['id'] != args.step:
        raise ValueError('select the next unfinished checkpoint')
    step = steps[index]
    previous = [a for a in state['attempts'] if a['id'] == args.step]
    if previous and not args.retry:
        raise ValueError('incomplete attempt retained; explicit --retry required')
    if not previous and args.retry:
        raise ValueError('no failed attempt to retry')
    if len(previous) >= 4:
        raise ValueError('three additional retries exhausted')
    number = len(previous) + 1
    artifact = _attempt_artifact(args.step, number)
    task = dict(step, condition=manifest['condition'], run_mode=run_mode, evaluator_binding=binding)
    task['request'] = str((source.parent / step['request']).resolve())
    task.pop('check', None)
    if not journal.exists():
        root.mkdir(parents=True, exist_ok=False)
    metadata = root / 'tasks'
    metadata.mkdir(exist_ok=True)
    task_path = metadata / (args.step + '.json')
    if not task_path.exists():
        write_json(task_path, task)
    allocation = {'id': args.step, 'artifact': str(artifact), 'attempt': number}
    metadata = {'run_mode': run_mode, 'evaluator_binding': binding,
                'development_fingerprint': fingerprint}
    authorization = getattr(args, 'launch_authorization', None)
    if authorization is not None:
        allocation['launch_authorization'] = authorization
        metadata['launch_authorization'] = authorization
    state['attempts'].append(allocation)
    write_json(journal, state)
    result = run(task_path, executor, root / artifact,
        prior_snapshot=completed.get(ids[index-1]) if index else None,
        run_id=state['run_id'], sequence={'id': manifest['id'], 'version': manifest['version']},
        visible_request='\n\n'.join(requests[:index+1]), attempt=number, result_metadata=metadata)
    allocation.update(completed=result['completed'], outcome=result['outcome'])
    write_json(journal, state)
    return result


def run(task_path, executor, output, *, prior_snapshot, run_id, sequence, visible_request, attempt, result_metadata):
    """Execute one fresh developer session and preserve its snapshot; evaluation is separate."""
    task = json.loads(Path(task_path).read_text())
    snapshot_binding = getattr(executor, 'snapshot_binding', None)
    if prior_snapshot is not None:
        validate(prior_snapshot, runtime_image=snapshot_binding['image'] if snapshot_binding else None)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / 'workspace'
    if prior_snapshot is None:
        workspace.mkdir()
    else:
        shutil.copytree(prior_snapshot, workspace, symlinks=True)
    (output / 'request.txt').write_text(visible_request)
    result = {
        'schema_version': 1, 'run_id': run_id,
        'session_id': str(uuid.uuid4()), 'sequence': sequence,
        'task': {'id': task['id'], 'version': task['version']},
        'condition': task['condition'], 'attempt': attempt, 'checkpoint': task['id'],
        'outcome': 'incomplete', 'functional': 'unknown', 'security': 'unknown',
        'execution': {}, 'evaluation': {}, 'completed': False,
    }
    if set(result_metadata).intersection(result):
        raise ValueError('result metadata cannot replace controller result fields')
    result.update(result_metadata)
    save_result(output, result)
    try:
        with (output / 'executor.stdout').open('w') as stdout, (output / 'executor.stderr').open('w') as stderr:
            result['execution'] = executor.execute(workspace, visible_request, stdout, stderr)
    except (OSError, KeyboardInterrupt) as error:
        result['execution'] = {'exit_status': None, 'error': str(error) or 'controller interrupted'}
    if result['execution']['exit_status'] != 0:
        save_result(output, result)
        return result
    try:
        preserve(workspace, output / 'snapshot', runtime_binding=snapshot_binding)
    except (OSError, ValueError) as error:
        result['snapshot_error'] = str(error)
        save_result(output, result)
        return result
    result.update(outcome='pending_evaluation', completed=True)
    save_result(output, result)
    return result


def save_result(output, result):
    write_json(output / 'result.json', result)
    (output / 'report.md').write_text(
        f"Run {result['run_id']}\n\n"
        f"Task: {result['task']['id']} @ {result['task']['version']}\n\n"
        f"Condition: {result['condition']['id']} @ {result['condition']['version']}\n\n"
        f"Attempt: {result['attempt']}; checkpoint: {result['checkpoint']}\n\n"
        f"Outcome: {result['outcome']}\n\n"
        f"Functional: {result['functional']}; security: {result['security']}\n")
