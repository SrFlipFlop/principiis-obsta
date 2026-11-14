"""Checkpoint-boundary continuation with append-only attempt artifacts."""
import hashlib
import json
from pathlib import Path
import uuid
from .snapshot import validate
from .task import check_argv


def write_json(path, value):
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def execute_sequence(source, manifest, requests, executor, output, run, *, resume, retry_incomplete):
    output = Path(output).resolve()
    if retry_incomplete and not resume:
        raise ValueError('--retry-incomplete requires --resume')
    # Freeze content as well as declared versions; changing unversioned requests or
    # check code must not silently combine incompatible observations.
    files = {}
    for step in manifest['steps']:
        for arg in step['check']:
            path = source.parent / arg
            if path.is_file():
                files[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    configuration = executor if isinstance(executor, list) else {'config': executor.config, 'version': executor.version}
    contract = {'manifest': manifest, 'requests': requests, 'checks': files, 'execution': configuration}
    fingerprint = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    identity = {'id': manifest['id'], 'version': manifest['version']}
    if resume:
        summary = json.loads((output / 'sequence.json').read_text())
        if summary.get('fingerprint') != fingerprint:
            raise ValueError('task or execution configuration mismatch; create a new run')
        for checkpoint in summary['checkpoints']:
            if checkpoint['outcome'] != 'incomplete':
                validate(output / checkpoint['artifact'] / 'snapshot')
        if summary['status'] == 'completed':
            return summary
    else:
        output.mkdir(parents=True, exist_ok=False)
        summary = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'sequence': identity,
                   'condition': manifest['condition'], 'checkpoints': [], 'status': 'running',
                   'fingerprint': fingerprint, 'active_attempt': None}
        write_json(output / 'sequence.json', summary)
    prior_snapshot = None
    completed = set()
    for checkpoint in summary['checkpoints']:
        if checkpoint['outcome'] != 'incomplete':
            completed.add(checkpoint['id'])
            prior_snapshot = output / checkpoint['artifact'] / 'snapshot'
    active = summary.get('active_attempt')
    if active:
        # Recover a fully recorded checkpoint even if the controller died before
        # updating the sequence journal; never rerun already completed work.
        result_path = output / active['artifact'] / 'result.json'
        result = json.loads(result_path.read_text()) if result_path.exists() else {}
        finished = result.get('completed') is True
        outcome = result['outcome'] if finished else 'incomplete'
        summary['checkpoints'].append(dict(active, outcome=outcome))
        if finished:
            validate(output / active['artifact'] / 'snapshot')
            completed.add(active['id'])
            prior_snapshot = output / active['artifact'] / 'snapshot'
        summary['active_attempt'] = None
        summary['status'] = 'incomplete'
        write_json(output / 'sequence.json', summary)
    incomplete = any(item['outcome'] == 'incomplete' and item['id'] not in completed for item in summary['checkpoints'])
    if incomplete and not retry_incomplete:
        raise ValueError('incomplete attempt retained; explicit --retry-incomplete required')
    for index, step in enumerate(manifest['steps']):
        if step['id'] in completed:
            continue
        previous = [item for item in summary['checkpoints'] if item['id'] == step['id']]
        attempt = len(previous) + 1
        destination = output / 'steps' / step['id'] if attempt == 1 else output / 'attempts' / step['id'] / str(attempt)
        task = dict(step, condition=manifest['condition'])
        task['request'] = str((source.parent / step['request']).resolve())
        task['check'] = check_argv(source.parent, step['check'])
        metadata = output / 'tasks'
        metadata.mkdir(exist_ok=True)
        task_path = metadata / (step['id'] + '.json')
        if not task_path.exists():
            write_json(task_path, task)
        record = {'id': step['id'], 'artifact': str(destination.relative_to(output))}
        summary['active_attempt'] = record
        summary['status'] = 'running'
        write_json(output / 'sequence.json', summary)
        result = run(task_path, executor, destination, prior_snapshot=prior_snapshot,
                     run_id=summary['run_id'], sequence=identity,
                     visible_request='\n\n'.join(requests[:index + 1]), attempt=attempt)
        summary['checkpoints'].append(dict(record, outcome=result['outcome']))
        summary['active_attempt'] = None
        summary['status'] = 'incomplete' if result['outcome'] == 'incomplete' else 'running'
        write_json(output / 'sequence.json', summary)
        if result['outcome'] == 'incomplete':
            return summary
        prior_snapshot = destination / 'snapshot'
    summary['status'] = 'completed'
    write_json(output / 'sequence.json', summary)
    return summary
