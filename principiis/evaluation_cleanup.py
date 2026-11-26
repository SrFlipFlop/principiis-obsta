"""Explicit cleanup receipts without rewriting retained primary assessments."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import uuid

from .development_runtime import docker_command, docker_environment
from .jsonio import write_json


def _allocation(root, assessment):
    path = Path(assessment['artifact']).parent / 'restricted/runtime-allocation.json'
    expected = root / 'development/evaluations' / assessment['checkpoint'] / str(assessment['attempt']) / 'restricted/runtime-allocation.json'
    if path != expected or path.resolve() != path:
        raise ValueError('evaluation runtime allocation must remain in canonical controller evidence')
    allocation = json.loads(path.read_text())
    if not isinstance(allocation, dict):
        raise ValueError('invalid evaluation runtime allocation')
    names = allocation.get('containers')
    if (not isinstance(names, dict) or set(names) != {'application', 'evaluator'}
            or not re.fullmatch(r'po-app-[0-9a-f]{32}', names['application'])
            or not re.fullmatch(r'po-eval-[0-9a-f]{32}', names['evaluator'])):
        raise ValueError('retained evaluation container identities are unavailable')
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), names


def pending(root, assessments):
    root = Path(root).resolve()
    index = root / 'evaluation-cleanups/index.json'
    receipts = []
    if index.exists():
        if index.is_symlink():
            raise ValueError('evaluation cleanup index cannot be a symlink')
        for relative in json.loads(index.read_text()):
            path = root / relative
            if path.resolve() != path or path.parent != root / 'evaluation-cleanups':
                raise ValueError('evaluation cleanup receipt must remain in controller evidence')
            if path.is_file():
                receipts.append(json.loads(path.read_text()))
    unresolved = []
    for assessment in assessments:
        if assessment.get('cleanup_pending') is not True:
            continue
        entry = {key: assessment[key] for key in ('artifact', 'checkpoint', 'attempt', 'session_id')}
        try:
            path, digest, containers = _allocation(root, assessment)
            if any(receipt.get('outcome') == 'removed'
                   and receipt.get('session_id') == assessment['session_id']
                   and receipt.get('runtime_allocation_sha256') == digest for receipt in receipts):
                continue
            entry.update(runtime_allocation=str(path), runtime_allocation_sha256=digest, containers=containers)
        except (OSError, ValueError, TypeError, KeyError) as error:
            entry['error'] = str(error)
        unresolved.append(entry)
    return unresolved


def cleanup(root, assessments, step):
    root = Path(root).resolve()
    selected = [entry for entry in pending(root, assessments) if entry['checkpoint'] == step]
    if not selected:
        raise ValueError('no unresolved evaluation runtime cleanup for selected checkpoint')
    if any('error' in entry for entry in selected):
        raise ValueError('evaluation container identities unavailable; inspect retained runtime evidence before cleanup')
    docker = json.loads((root / 'runtime.json').read_text())['docker']
    directory = root / 'evaluation-cleanups'
    directory.mkdir(exist_ok=True)
    index = directory / 'index.json'
    ledger = json.loads(index.read_text()) if index.exists() else []
    records = []
    for entry in selected:
        path = directory / (uuid.uuid4().hex + '.json')
        record = dict(entry, outcome='interrupted_cleanup', commands=[], started_at=time.time())
        ledger.append(str(path.relative_to(root)))
        write_json(index, ledger)
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
