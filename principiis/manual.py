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


def develop(args):
    source = Path(args.sequence).resolve()
    manifest = json.loads(source.read_text())
    steps = manifest['steps']
    ids = [s['id'] for s in steps]
    if len(set(ids)) != len(ids) or any(Path(i).name != i or i in ('.', '..') for i in ids):
        raise ValueError('unsafe or duplicate step identity')
    if not manifest.get('id') or not manifest.get('version') or not isinstance(manifest.get('condition'), dict):
        raise ValueError('sequence and condition identity/version required')
    if not steps or any(s.get('sequence_version') != manifest['version'] or not s.get('version') or not s.get('check') for s in steps):
        raise ValueError('invalid step version or evaluator command')
    if args.step not in ids:
        raise ValueError('unknown checkpoint')
    requests = [(source.parent / s['request']).read_text() for s in steps]
    root = Path(args.output).resolve()
    if args.codex_config:
        from .codex import Codex
        executor = Codex(args.codex_config, root, source.parent)
        configuration = {'config': executor.config, 'version': executor.version}
    else:
        executor = json.loads(args.executor)
        configuration = executor
    fingerprint = hashlib.sha256(json.dumps([manifest, requests, configuration], sort_keys=True).encode()).hexdigest()
    journal = root / 'manual.json'
    if journal.exists():
        state = json.loads(journal.read_text())
        if state['fingerprint'] != fingerprint:
            raise ValueError('sequence or execution configuration changed; use a new run')
    else:
        root.mkdir(parents=True, exist_ok=False)
        state = {'run_id': str(uuid.uuid4()), 'fingerprint': fingerprint, 'attempts': []}
    # Reconcile a process interruption after the immutable result was recorded.
    completed = {}
    for record in state['attempts']:
        result_path = root / record['artifact'] / 'result.json'
        if result_path.exists() and json.loads(result_path.read_text()).get('completed'):
            validate(result_path.parent / 'snapshot')
            completed[record['id']] = result_path.parent / 'snapshot'
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
    artifact = Path('steps') / args.step if number == 1 else Path('attempts') / args.step / str(number)
    task = dict(step, condition=manifest['condition'])
    task['request'] = str((source.parent / step['request']).resolve())
    task['check'] = check_argv(source.parent, step['check'])
    metadata = root / 'tasks'
    metadata.mkdir(exist_ok=True)
    task_path = metadata / (args.step + '.json')
    if not task_path.exists():
        write_json(task_path, task)
    state['attempts'].append({'id': args.step, 'artifact': str(artifact), 'attempt': number})
    write_json(journal, state)
    run(task_path, executor, root / artifact,
        prior_snapshot=completed.get(ids[index-1]) if index else None,
        run_id=state['run_id'], sequence={'id': manifest['id'], 'version': manifest['version']},
        visible_request='\n\n'.join(requests[:index+1]), attempt=number, defer_evaluation=True)


def evaluate(args):
    root = Path(args.output).resolve()
    state = json.loads((root / 'manual.json').read_text())
    candidates = [root/a['artifact'] for a in state['attempts'] if a['id'] == args.step]
    completed = [p for p in candidates if (p/'result.json').exists() and json.loads((p/'result.json').read_text()).get('completed')]
    if not completed:
        raise ValueError('completed developer checkpoint required')
    checkpoint = completed[-1]
    snapshot = checkpoint / 'snapshot'
    task_path = root / 'tasks' / (args.step + '.json')
    task = json.loads(task_path.read_text())
    check = task['check']
    provenance = {'version': args.evaluator_version, 'argv': check,
                  'files': {str(Path(a).resolve()): sha(a) for a in check if Path(a).is_file()}}
    if not args.evaluator_version:
        raise ValueError('nonempty evaluator version required')
    parent = root / 'evaluations' / args.step
    parent.mkdir(parents=True, exist_ok=True)
    for historical in parent.glob('*/result.json'):
        previous = json.loads(historical.read_text())
        if previous['provenance']['version'] == args.evaluator_version and previous['provenance'] != provenance:
            raise ValueError('evaluator content changed; select a new evaluator version')
    number = len(list(parent.iterdir())) + 1
    output = parent / str(number)
    output.mkdir(exist_ok=False)
    result = {'schema_version': 1, 'run_id': state['run_id'], 'session_id': str(uuid.uuid4()),
              'stage': 'independent_evaluation', 'role': 'primary' if number == 1 else 'rerun',
              'attempt': number, 'checkpoint': args.step, 'provenance': provenance,
              'developer_result_sha256': sha(checkpoint/'result.json'),
              'snapshot': str(snapshot), 'snapshot_manifest_sha256': sha(snapshot.with_suffix('.json')) if snapshot.with_suffix('.json').exists() else None, 'outcome': 'evaluator_error',
              'functional': 'unknown', 'security': 'unknown', 'evaluation': {}}
    write_json(output/'result.json', result)
    try:
        validate(snapshot)
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
    dev.add_argument('--retry', action='store_true')
    ev = sub.add_parser('evaluate')
    ev.add_argument('--evaluator-version', required=True)
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
