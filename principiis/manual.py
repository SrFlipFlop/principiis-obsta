"""Explicit single-checkpoint development and append-only primary evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import signal
import tempfile
import uuid

from .__main__ import run, evaluator_scores
from .execution import execute
from .resume import write_json
from .snapshot import validate
from .task import check_argv


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and '\0' not in value


def _argv(value):
    return isinstance(value, list) and bool(value) and all(_text(arg) for arg in value)


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


def _development_contract(source, development_only):
    """Validate requests independently of evaluator readiness, before allocation."""
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
        if ('check' in step and not _argv(step['check'])) or ('check' not in step and not development_only):
            raise ValueError('valid evaluator command required unless --development-only is explicit')
        if not _text(step.get('request')):
            raise ValueError('request file path required')
        requests.append((source.parent / step['request']).read_text())
    return manifest, requests


def develop(args):
    source = Path(args.sequence).resolve()
    development_only = getattr(args, 'development_only', False)
    manifest, requests = _development_contract(source, development_only)
    steps = manifest['steps']
    ids = [s['id'] for s in steps]
    if args.step not in ids:
        raise ValueError('unknown checkpoint')
    root = Path(args.output).resolve()
    runtime_config = getattr(args, 'runtime_config', None)
    codex_config = getattr(args, 'codex_config', None)
    fixture_executor = getattr(args, 'executor', None)
    if sum(value is not None for value in (runtime_config, codex_config, fixture_executor)) != 1:
        raise ValueError('select exactly one runtime, Codex configuration or fixture executor')
    if runtime_config:
        from .development_runtime import DevelopmentRuntime
        executor = DevelopmentRuntime(runtime_config, root, source.parent)
        configuration = {'config': executor.config, 'version': executor.version}
    elif codex_config:
        from .codex import Codex
        executor = Codex(codex_config, root, source.parent)
        configuration = {'config': executor.config, 'version': executor.version}
    else:
        executor = json.loads(fixture_executor)
        if not _argv(executor):
            raise ValueError('fixture executor must be a nonempty argv array')
        configuration = executor
    if development_only:
        frozen_manifest = dict(manifest, steps=[{key: value for key, value in step.items() if key != 'check'}
                                               for step in steps])
        contract = [frozen_manifest, requests, configuration, {'run_mode': 'development-rehearsal'}]
    else:
        check_files = {str((source.parent / a).resolve()): sha(source.parent / a)
                       for step in steps for a in step['check'] if (source.parent / a).is_file()}
        contract = [manifest, requests, configuration, check_files]
    fingerprint = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    run_mode = 'development-rehearsal' if development_only else 'baseline'
    binding = 'unbound' if development_only else 'task-contract'
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
    if development_only:
        task.pop('check', None)
    else:
        task['check'] = check_argv(source.parent, step['check'])
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
        visible_request='\n\n'.join(requests[:index+1]), attempt=number, defer_evaluation=True,
        result_metadata=metadata)
    allocation.update(completed=result['completed'], outcome=result['outcome'])
    write_json(journal, state)
    return result


def evaluate(args):
    root = Path(args.output).resolve()
    state = json.loads((root / 'manual.json').read_text())
    if not isinstance(state, dict):
        raise ValueError('invalid manual journal')
    if state.get('evaluator_binding') == 'unbound':
        raise ValueError('development rehearsal evaluator is unbound; explicit versioned binding is required before evaluation')
    attempts, _ = _journal_attempts(root, state)
    completed = [directory for record, directory, result in attempts
                 if record['id'] == args.step and result and result.get('completed') is True]
    if not completed:
        raise ValueError('completed developer checkpoint required')
    checkpoint = completed[-1]
    snapshot = checkpoint / 'snapshot'
    task_path = root / 'tasks' / (args.step + '.json')
    task = json.loads(task_path.read_text())
    check = task['check']
    if not args.evaluator_version:
        raise ValueError('nonempty evaluator version required')
    declaration = Path(args.evaluator_manifest).resolve()
    bundle = json.loads(declaration.read_text())
    if bundle.get('version') != args.evaluator_version or bundle.get('complete') is not True or not bundle.get('files'):
        raise ValueError('complete versioned evaluator dependency manifest required')
    files = {}
    for relative, digest in bundle['files'].items():
        path = (declaration.parent / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(declaration.parent):
            raise ValueError('evaluator manifest paths must stay within its directory')
        if sha(path) != digest:
            raise ValueError('evaluator manifest file content changed; select a new evaluator version')
        files[str(path)] = digest
    if any(str(Path(a).resolve()) not in files for a in check[1:] if Path(a).is_file()):
        raise ValueError('evaluator command file absent from dependency manifest')
    provenance = {'version': args.evaluator_version, 'argv': check, 'files': files,
                  'manifest_sha256': sha(declaration),
                  'executable_sha256': sha(check[0]) if Path(check[0]).is_file() else None}
    parent = root / 'evaluations' / args.step
    parent.mkdir(parents=True, exist_ok=True)
    ledger_path = parent / 'allocations.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    # A legacy orphan has no recoverable identity or provenance. Preserve that fact.
    known = {entry['attempt'] for entry in ledger}
    for directory in sorted(parent.iterdir()):
        if directory.is_dir() and directory.name.isdecimal() and int(directory.name) not in known:
            existing = directory / 'result.json'
            if existing.exists():
                ledger.append(json.loads(existing.read_text()))
            else:
                ledger.append({'schema_version': 1, 'attempt': int(directory.name),
                               'role': 'primary' if directory.name == '1' else 'rerun',
                               'stage': 'independent_evaluation', 'checkpoint': args.step,
                               'run_id': None, 'session_id': None, 'developer_result_sha256': None,
                               'allocation_provenance': 'unknown_legacy',
                               'provenance': {'version': None}, 'outcome': 'evaluator_error',
                               'functional': 'unknown', 'security': 'unknown', 'evaluation': {},
                               'error': 'interrupted legacy allocation; identity and provenance unknown'})
    for entry in ledger:
        directory = parent / str(entry['attempt'])
        directory.mkdir(exist_ok=True)
        if not (directory/'result.json').exists():
            write_json(directory/'result.json', dict(entry, error=entry.get('error', 'controller interrupted after allocation')))
    write_json(ledger_path, ledger)
    for historical in parent.glob('*/result.json'):
        previous = json.loads(historical.read_text())
        if previous['provenance']['version'] == args.evaluator_version and previous['provenance'] != provenance:
            raise ValueError('evaluator content changed; select a new evaluator version')
    number = max((e['attempt'] for e in ledger), default=0) + 1
    output = parent / str(number)
    result = {'schema_version': 1, 'run_id': state['run_id'], 'session_id': str(uuid.uuid4()),
              'stage': 'independent_evaluation', 'role': 'primary' if number == 1 else 'rerun',
              'attempt': number, 'checkpoint': args.step, 'provenance': provenance,
              'developer_result_sha256': sha(checkpoint/'result.json'),
              'snapshot': str(snapshot), 'snapshot_manifest_sha256': sha(snapshot.with_suffix('.json')) if snapshot.with_suffix('.json').exists() else None, 'outcome': 'evaluator_error',
              'functional': 'unknown', 'security': 'unknown', 'evaluation': {}}
    ledger.append(result)
    write_json(ledger_path, ledger)
    output.mkdir(exist_ok=False)
    write_json(output/'result.json', result)
    try:
        validate(snapshot, runtime_image=None)
        with tempfile.TemporaryDirectory(prefix='principiis-primary-') as d:
            candidate = Path(d)/'candidate'
            shutil.copytree(snapshot, candidate, symlinks=True)
            with (output/'evaluator.stdout').open('w') as stdout, (output/'evaluator.stderr').open('w') as stderr:
                result['evaluation'] = execute(check, candidate, '', stdout, stderr)
        if result['evaluation']['exit_status'] != 0:
            raise ValueError('predefined evaluator failed')
        result.update(evaluator_scores(json.loads((output/'evaluator.stdout').read_text())))
    except (OSError, ValueError, TypeError, KeyboardInterrupt) as error:
        result['error'] = str(error) or 'controller interrupted'
    finally:
        write_json(output/'result.json', result)


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    dev = sub.add_parser('develop')
    dev.add_argument('--sequence', required=True)
    selection = dev.add_mutually_exclusive_group(required=True)
    selection.add_argument('--executor')
    selection.add_argument('--codex-config')
    selection.add_argument('--runtime-config', help='Reviewed isolated subscription runtime configuration')
    dev.add_argument('--development-only', action='store_true',
                     help='Record an unbound development rehearsal without requiring evaluator commands')
    dev.add_argument('--retry', action='store_true')
    ev = sub.add_parser('evaluate')
    ev.add_argument('--evaluator-version', required=True)
    ev.add_argument('--evaluator-manifest', required=True)
    for command in (dev, ev):
        command.add_argument('--output', required=True)
        command.add_argument('--step', required=True)
    args = parser.parse_args()
    try:
        (develop if args.command == 'develop' else evaluate)(args)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))

if __name__ == '__main__':
    main()
