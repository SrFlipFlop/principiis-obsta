import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid


def run(task_path, executor, output):
    task_path = Path(task_path).resolve()
    task = json.loads(task_path.read_text())
    request = (task_path.parent / task['request']).read_text()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / 'workspace'
    workspace.mkdir()
    (output / 'request.txt').write_text(request)
    result = {
        'schema_version': 1, 'run_id': str(uuid.uuid4()),
        'task': {'id': task['id'], 'version': task['version']},
        'condition': task['condition'], 'attempt': 1, 'checkpoint': task['id'],
        'outcome': 'incomplete', 'functional': 'unknown', 'security': 'unknown',
        'execution': {}, 'evaluation': {},
    }
    started = time.monotonic()
    save_result(output, result)
    try:
        with (output / 'executor.stdout').open('w') as stdout, (output / 'executor.stderr').open('w') as stderr:
            process = subprocess.run(executor, cwd=workspace, input=request, text=True, stdout=stdout, stderr=stderr)
        result['execution'] = {'argv': executor, 'exit_status': process.returncode}
    except (OSError, KeyboardInterrupt) as error:
        result['execution'] = {'argv': executor, 'exit_status': None,
                               'error': str(error) or 'controller interrupted'}
    result['execution']['elapsed_seconds'] = time.monotonic() - started
    if result['execution']['exit_status'] != 0:
        save_result(output, result)
        return result
    shutil.copytree(workspace, output / 'snapshot', symlinks=True)
    check = list(task['check'])
    # Relative existing file arguments belong to the task package, not the candidate.
    check = [str((task_path.parent / arg).resolve()) if (task_path.parent / arg).is_file() else arg for arg in check]
    result['outcome'] = 'evaluator_error'
    result['evaluation'] = {'argv': check, 'exit_status': None}
    save_result(output, result)
    evaluation_started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix='principiis-evaluation-') as evaluation:
            candidate = Path(evaluation) / 'candidate'
            shutil.copytree(output / 'snapshot', candidate, symlinks=True)
            checked = subprocess.run(check, cwd=candidate, text=True, capture_output=True)
        (output / 'evaluator.stdout').write_text(checked.stdout)
        (output / 'evaluator.stderr').write_text(checked.stderr)
        result['evaluation']['exit_status'] = checked.returncode
        if checked.returncode != 0:
            raise ValueError('evaluator exited unsuccessfully')
        scores = json.loads(checked.stdout)
        if not isinstance(scores, dict) or any(scores.get(key) not in ('pass', 'fail', 'unassessable') for key in ('functional', 'security')):
            raise ValueError('invalid evaluator scores')
        result.update({key: scores[key] for key in ('functional', 'security')})
        result['outcome'] = ('joint_pass' if scores['functional'] == scores['security'] == 'pass'
                             else 'candidate_failure' if 'fail' in (scores['functional'], scores['security']) else 'unassessable')
    except (OSError, ValueError, TypeError, KeyboardInterrupt) as error:
        result['evaluation']['error'] = str(error) or 'controller interrupted'
    result['evaluation']['elapsed_seconds'] = time.monotonic() - evaluation_started
    save_result(output, result)
    return result


def save_result(output, result):
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'report.md').write_text(
        f"Run {result['run_id']}\n\n"
        f"Task: {result['task']['id']} @ {result['task']['version']}\n\n"
        f"Condition: {result['condition']['id']} @ {result['condition']['version']}\n\n"
        f"Attempt: {result['attempt']}; checkpoint: {result['checkpoint']}\n\n"
        f"Outcome: {result['outcome']}\n\n"
        f"Functional: {result['functional']}; security: {result['security']}\n")


def main():
    parser = argparse.ArgumentParser(description='Local fixture checkpoint controller')
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('run')
    command.add_argument('--task', required=True)
    command.add_argument('--executor', required=True, help='JSON argv array; receives visible request on stdin')
    command.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.task, json.loads(args.executor), args.output)


if __name__ == '__main__':
    main()
