import argparse
from .execution import execute
from .snapshot import preserve, validate
from .task import check_argv
import json
from pathlib import Path
import shutil
import signal
import tempfile
import uuid


def run(task_path, executor, output, *, prior_snapshot=None, run_id=None, sequence=None, visible_request=None, attempt=1):
    task_path = Path(task_path).resolve()
    task = json.loads(task_path.read_text())
    request = visible_request if visible_request is not None else (task_path.parent / task['request']).read_text()
    if prior_snapshot is not None:
        validate(prior_snapshot)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / 'workspace'
    if prior_snapshot is None:
        workspace.mkdir()
    else:
        shutil.copytree(prior_snapshot, workspace, symlinks=True)
    (output / 'request.txt').write_text(request)
    result = {
        'schema_version': 1, 'run_id': run_id or str(uuid.uuid4()),
        'session_id': str(uuid.uuid4()), 'sequence': sequence,
        'task': {'id': task['id'], 'version': task['version']},
        'condition': task['condition'], 'attempt': attempt, 'checkpoint': task['id'],
        'outcome': 'incomplete', 'functional': 'unknown', 'security': 'unknown',
        'execution': {}, 'evaluation': {}, 'completed': False,
    }
    save_result(output, result)
    try:
        with (output / 'executor.stdout').open('w') as stdout, (output / 'executor.stderr').open('w') as stderr:
            if hasattr(executor, 'execute'):
                result['execution'] = executor.execute(workspace, request, stdout, stderr)
            else:
                result['execution'] = execute(executor, workspace, request, stdout, stderr)
    except (OSError, KeyboardInterrupt) as error:
        result['execution'] = {'argv': executor, 'exit_status': None,
                               'error': str(error) or 'controller interrupted'}
    if result['execution']['exit_status'] != 0:
        save_result(output, result)
        return result
    try:
        preserve(workspace, output / 'snapshot')
    except (OSError, ValueError) as error:
        result['snapshot_error'] = str(error)
        save_result(output, result)
        return result
    check = list(task['check'])
    # Relative existing file arguments belong to the task package, not the candidate.
    check = check_argv(task_path.parent, check)
    result['outcome'] = 'evaluator_error'
    result['evaluation'] = {'argv': check, 'exit_status': None}
    save_result(output, result)
    try:
        with tempfile.TemporaryDirectory(prefix='principiis-evaluation-') as evaluation:
            validate(output / 'snapshot')
            candidate = Path(evaluation) / 'candidate'
            shutil.copytree(output / 'snapshot', candidate, symlinks=True)
            with (output / 'evaluator.stdout').open('w') as stdout, (output / 'evaluator.stderr').open('w') as stderr:
                result['evaluation'] = execute(check, candidate, '', stdout, stderr)
        if result['evaluation']['exit_status'] != 0:
            raise ValueError('evaluator exited unsuccessfully')
        scores = json.loads((output / 'evaluator.stdout').read_text())
        if not isinstance(scores, dict) or any(scores.get(key) not in ('pass', 'fail', 'unassessable') for key in ('functional', 'security')):
            raise ValueError('invalid evaluator scores')
        result.update({key: scores[key] for key in ('functional', 'security')})
        result['outcome'] = ('joint_pass' if scores['functional'] == scores['security'] == 'pass'
                             else 'candidate_failure' if 'fail' in (scores['functional'], scores['security']) else 'unassessable')
    except (OSError, ValueError, TypeError, KeyboardInterrupt) as error:
        result['evaluation']['error'] = str(error) or 'controller interrupted'
    result['completed'] = True
    save_result(output, result)
    return result


def save_result(output, result):
    from .resume import write_json
    write_json(output / 'result.json', result)
    (output / 'report.md').write_text(
        f"Run {result['run_id']}\n\n"
        f"Task: {result['task']['id']} @ {result['task']['version']}\n\n"
        f"Condition: {result['condition']['id']} @ {result['condition']['version']}\n\n"
        f"Attempt: {result['attempt']}; checkpoint: {result['checkpoint']}\n\n"
        f"Outcome: {result['outcome']}\n\n"
        f"Functional: {result['functional']}; security: {result['security']}\n")


def run_sequence(sequence_path, executor, output, *, resume=False, retry_incomplete=False, stop_requested=lambda: False):
    sequence_path = Path(sequence_path).resolve()
    manifest = json.loads(sequence_path.read_text())
    condition = manifest.get('condition')
    if not isinstance(condition, dict) or not condition.get('id') or not condition.get('version'):
        raise ValueError('condition identity and version required')
    steps = manifest['steps']
    if not steps:
        raise ValueError('sequence must have steps')
    identifiers = [step.get('id') for step in steps]
    if any(not isinstance(key, str) or not key or Path(key).name != key or key in ('.', '..') for key in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError('missing, unsafe or duplicate step identifiers')
    if not manifest.get('id') or not manifest.get('version'):
        raise ValueError('sequence identity and version required')
    if any(step.get('sequence_version') != manifest['version'] for step in steps):
        raise ValueError('inconsistent sequence versions')
    # Preflight every task before creating artifacts or starting any executor.
    requests = []
    for step in steps:
        if not step.get('version') or not isinstance(step.get('check'), list) or not step['check'] or not all(isinstance(arg, str) for arg in step['check']):
            raise ValueError('invalid step version or check argv')
        requests.append((sequence_path.parent / step['request']).read_text())
    from .resume import execute_sequence
    return execute_sequence(sequence_path, manifest, requests, executor, output, run,
                            resume=resume, retry_incomplete=retry_incomplete, stop_requested=stop_requested)


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt('controller interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description='Local fixture checkpoint controller')
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('run')
    command.add_argument('--task', required=True)
    selection = command.add_mutually_exclusive_group(required=True)
    selection.add_argument('--executor', help='JSON argv array; receives visible request on stdin')
    selection.add_argument('--codex-config', help='Explicit clean ordinary Codex configuration JSON')
    command.add_argument('--output', required=True)
    sequence_command = sub.add_parser('sequence')
    sequence_command.add_argument('--sequence', required=True)
    selection = sequence_command.add_mutually_exclusive_group(required=True)
    selection.add_argument('--executor')
    selection.add_argument('--codex-config')
    sequence_command.add_argument('--output', required=True)
    sequence_command.add_argument('--resume', action='store_true')
    sequence_command.add_argument('--retry-incomplete', action='store_true')
    args = parser.parse_args()
    if args.codex_config:
        from .codex import Codex
        executor = Codex(args.codex_config, args.output, Path(args.sequence if args.command == 'sequence' else args.task).parent)
    else:
        executor = json.loads(args.executor)
    if args.command == 'sequence':
        run_sequence(args.sequence, executor, args.output, resume=args.resume, retry_incomplete=args.retry_incomplete)
    else:
        run(args.task, executor, args.output)


if __name__ == '__main__':
    main()
