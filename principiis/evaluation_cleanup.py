"""Explicit cleanup receipts without rewriting retained primary assessments."""
from pathlib import Path
import re
import subprocess
import time
import uuid

from .development_runtime import docker_command, docker_environment
from .jsonio import digest, write_json


def _allocation(store, assessment):
    path = Path(assessment['artifact']).parent / 'restricted/runtime-allocation.json'
    expected = store.development / 'evaluations' / assessment['checkpoint'] / str(assessment['attempt']) / 'restricted/runtime-allocation.json'
    if path != expected or path.resolve() != path:
        raise ValueError('evaluation runtime allocation must remain in canonical controller evidence')
    allocation = store.record(path)
    if not isinstance(allocation, dict):
        raise ValueError('invalid evaluation runtime allocation')
    names = allocation.get('containers')
    if (not isinstance(names, dict) or set(names) != {'application', 'evaluator'}
            or not re.fullmatch(r'po-app-[0-9a-f]{32}', names['application'])
            or not re.fullmatch(r'po-eval-[0-9a-f]{32}', names['evaluator'])):
        raise ValueError('retained evaluation container identities are unavailable')
    return path, digest(path), names


def pending(store):
    """Assessments whose evaluation containers may remain, without a matching removal receipt."""
    receipts = store.records('evaluation-cleanups')
    unresolved = []
    for assessment in store.assessments:
        if assessment.get('cleanup_pending') is not True:
            continue
        entry = {key: assessment[key] for key in ('artifact', 'checkpoint', 'attempt', 'session_id')}
        try:
            path, allocation_sha256, containers = _allocation(store, assessment)
            if any(receipt.get('outcome') == 'removed'
                   and receipt.get('session_id') == assessment['session_id']
                   and receipt.get('runtime_allocation_sha256') == allocation_sha256 for receipt in receipts):
                continue
            entry.update(runtime_allocation=str(path), runtime_allocation_sha256=allocation_sha256, containers=containers)
        except (OSError, ValueError, TypeError, KeyError) as error:
            entry['error'] = str(error)
        unresolved.append(entry)
    return unresolved


def cleanup(store, step):
    selected = [entry for entry in pending(store) if entry['checkpoint'] == step]
    if not selected:
        raise ValueError('no unresolved evaluation runtime cleanup for selected checkpoint')
    if any('error' in entry for entry in selected):
        raise ValueError('evaluation container identities unavailable; inspect retained runtime evidence before cleanup')
    docker = store.frozen('runtime.json')['docker']
    records = []
    for entry in selected:
        relative = f'evaluation-cleanups/{uuid.uuid4().hex}.json'
        path = store.root / relative
        record = dict(entry, outcome='interrupted_cleanup', commands=[], started_at=time.time())
        store.add_record('evaluation-cleanups', relative)
        write_json(path, record)
        started = time.monotonic()
        errors = []
        try:
            for name in reversed(list(entry['containers'].values())):
                command = {'argv': docker_command(docker, ['rm', '-f', name])}
                record['commands'].append(command)
                write_json(path, record)
                try:
                    removed = subprocess.run(command['argv'], capture_output=True, text=True,
                                             timeout=20, env=docker_environment())
                    command.update(stdout=removed.stdout, stderr=removed.stderr, exit_status=removed.returncode)
                    absent = bool(re.fullmatch(r'(?:Error response from daemon: )?No such container: '
                                              + re.escape(name), removed.stderr.strip()))
                    command['absent_before_cleanup'] = absent
                    if removed.returncode and not absent:
                        raise ValueError('Docker cleanup failed; see retained command stderr')
                except subprocess.TimeoutExpired as error:
                    command.update(error='Docker cleanup timed out',
                                   stdout=(error.stdout or b'').decode(errors='replace') if isinstance(error.stdout, bytes) else error.stdout,
                                   stderr=(error.stderr or b'').decode(errors='replace') if isinstance(error.stderr, bytes) else error.stderr)
                    errors.append(command['error'])
                except (OSError, ValueError, RuntimeError) as error:
                    command['error'] = str(error)
                    errors.append(str(error))
            record.update(outcome='cleanup_error' if errors else 'removed', errors=errors)
        finally:
            record.update(finished_at=time.time(), elapsed_seconds=time.monotonic() - started)
            write_json(path, record)
        records.append(record)
    return records
