"""Restricted, model-free checkpoint assessment. Never launches candidate code on host."""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import os
import stat
import signal
import subprocess
import time
import uuid
from .snapshot import validate, inventory
from .resume import write_json
from .development_runtime import docker_environment, docker_command


def digest(path, *, runtime_image=None):
    if not path.is_dir():
        raise ValueError('snapshot must be an existing directory')
    if path.with_suffix('.json').exists():
        validate(path, runtime_image=runtime_image)
        # Retained manifests define lexical file/link semantics, including image-bound
        # interpreters. Hash that verified inventory without resolving links on host.
        return hashlib.sha256(json.dumps(inventory(path, runtime_binding={
            'image': runtime_image, 'symlink_targets': [item['link'] for item in json.loads(path.with_suffix('.json').read_text()).values()
            if item.get('runtime_image') == runtime_image]} if runtime_image else None), sort_keys=True).encode()).hexdigest()
    value = hashlib.sha256()
    for item in sorted(path.rglob('*')):
        if item.is_symlink():
            raise ValueError('snapshot symlinks are unsupported')
        if item.is_file():
            value.update(str(item.relative_to(path)).encode() + b'\0' + item.read_bytes())
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--snapshot', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--app-image', required=True)
    parser.add_argument('--app-command', help='Candidate startup JSON argv; mounts the retained tree at /workspace')
    parser.add_argument('--evaluator-image', required=True)
    parser.add_argument('--version', default='engineering-1')
    parser.add_argument('--control', choices=['safe', 'ui-only', 'reject-all', 'alternative'], default='safe')
    parser.add_argument('--fixture-variant', help='author-only fixture mode; requires --check-contract and default --control')
    parser.add_argument('--check-contract', type=pathlib.Path, help='author-only JSON mapping of required check IDs to functional/security')
    parser.add_argument('--predecessor-snapshot', type=pathlib.Path, help='retained prior checkpoint for data continuation')
    parser.add_argument('--continuation-path', action='append', default=[], help='relative database file copied into disposable current application')
    parser.add_argument('--continuation-version', help='version of qualified data-continuation contract')
    parser.add_argument('--docker', default='docker')
    parser.add_argument('--seccomp', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1] / 'fixtures/evaluation/seccomp_profile.json')
    args = parser.parse_args()
    snapshot = args.snapshot.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    output.chmod(0o777)
    record = dict(schema_version=1, evaluator_version=args.version, snapshot_sha256=None, functional='unassessable', security='unassessable', outcome='evaluator_error', commands=[], control=args.control)
    names = ['po-app-' + uuid.uuid4().hex, 'po-eval-' + uuid.uuid4().hex]
    start = time.monotonic()
    app_started = False
    predecessor = None
    predecessor_digest = None
    record['containers'] = {'application': names[0], 'evaluator': names[1]}
    record['cleanup_argv'] = [docker_command(args.docker, ['rm', '-f', name]) for name in reversed(names)]
    record['resources_removed'] = False
    allocation_path = output / 'runtime-allocation.json'
    write_json(allocation_path, record)

    def interrupted(signum, _frame):
        record['interrupted_signal'] = signum
        raise KeyboardInterrupt('controller interrupted')

    signal.signal(signal.SIGTERM, interrupted)

    def run(arguments, timeout=120):
        command = docker_command(args.docker, arguments)
        record['commands'].append(command)
        index = len(record['commands'])
        write_json(allocation_path, record)
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=docker_environment())
        except subprocess.TimeoutExpired as error:
            for stream in ('stdout', 'stderr'):
                data = getattr(error, stream) or b''
                (output / f'{index}.{stream}').write_bytes(data.encode() if isinstance(data, str) else data)
            record.setdefault('exit_statuses', []).append('timeout')
            raise
        except KeyboardInterrupt:
            (output / f'{index}.stderr').write_text('controller interrupted during Docker command')
            record.setdefault('exit_statuses', []).append('interrupted')
            raise
        except OSError as error:
            (output / f'{index}.stderr').write_text(str(error))
            record.setdefault('exit_statuses', []).append('launch_error')
            raise
        (output / f'{index}.stdout').write_text(result.stdout)
        (output / f'{index}.stderr').write_text(result.stderr)
        record.setdefault('exit_statuses', []).append(result.returncode)
        write_json(allocation_path, record)
        absent = (arguments[:2] == ['rm', '-f'] and len(arguments) == 3
                  and re.fullmatch(r'(?:Error response from daemon: )?No such container: '
                                   + re.escape(arguments[2]), result.stderr.strip()))
        if absent:
            record.setdefault('absent_containers', []).append(arguments[2])
        if result.returncode and not absent:
            raise RuntimeError(f'command {index} exited {result.returncode}: {result.stderr[-2000:]}')
        return result.stdout

    try:
        record['snapshot_sha256'] = digest(snapshot, runtime_image=args.app_image)
        app_command = json.loads(args.app_command) if args.app_command else None
        if app_command is not None and (not isinstance(app_command, list) or not app_command
                or not all(isinstance(arg, str) and arg and '\0' not in arg for arg in app_command)):
            raise ValueError('candidate startup must be a nonempty JSON argv')
        if app_command is not None and (args.fixture_variant is not None or args.control != 'safe'):
            raise ValueError('candidate startup cannot select an author control')
        continuation = None
        if args.predecessor_snapshot or args.continuation_path or args.continuation_version:
            if not (args.predecessor_snapshot and args.continuation_path and args.continuation_version and app_command):
                raise ValueError('versioned predecessor, database paths and candidate startup are required together')
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', args.continuation_version):
                raise ValueError('invalid continuation version')
            predecessor = args.predecessor_snapshot.resolve()
            if not predecessor.with_suffix('.json').is_file():
                raise ValueError('retained predecessor snapshot manifest required')
            predecessor_digest = digest(predecessor, runtime_image=args.app_image)
            paths = []
            for name in args.continuation_path:
                relative = pathlib.PurePosixPath(name)
                if (not name or relative.is_absolute() or '..' in relative.parts or '.' in relative.parts
                        or str(relative) != name or name in paths):
                    raise ValueError('continuation database path must be unique and relative')
                source = predecessor / name
                if source.is_symlink() or not source.is_file() or source.resolve().parent != source.parent:
                    raise ValueError('continuation predecessor database must be a retained regular file')
                paths.append(name)
            continuation = {'version': args.continuation_version, 'predecessor_snapshot': str(predecessor),
                            'predecessor_sha256': predecessor_digest, 'paths': paths,
                            'files': {name: hashlib.sha256((predecessor / name).read_bytes()).hexdigest() for name in paths}}
            record['continuation'] = continuation
        record['app_command'] = app_command
        required = {name: kind for kind, names in [('functional', ['browser-own-read', 'api-own-read', 'api-own-update', 'integration-audit']), ('security', ['backend-cross-user-read', 'backend-cross-user-update'])] for name in names}
        if args.check_contract:
            raw = args.check_contract.read_bytes()
            required = json.loads(raw)
            if not isinstance(required, dict) or not all(isinstance(k, str) and k and v in ('functional', 'security') for k, v in required.items()) or set(required.values()) != {'functional', 'security'}:
                raise ValueError('invalid check contract: both functional and security checks required')
            record['check_contract_sha256'] = hashlib.sha256(raw).hexdigest()
        if args.fixture_variant is not None:
            if not args.check_contract or args.control != 'safe' or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', args.fixture_variant):
                raise ValueError('fixture variant requires an author check contract, default control and a lowercase alphanumeric/hyphen name')
            record['fixture_variant'] = args.fixture_variant
        record['evaluator_image'] = args.evaluator_image
        record['app_image'] = args.app_image
        record['seccomp_sha256'] = hashlib.sha256(args.seccomp.read_bytes()).hexdigest()
        for image in [args.app_image, args.evaluator_image]:
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
                raise ValueError('prepared images must be pinned by local sha256 image ID')
            details = json.loads(run(['image', 'inspect', image]))
            if not isinstance(details, list) or len(details) != 1 or details[0].get('Id') != image:
                raise ValueError('prepared image identity differs from the pinned runtime')
        common = ['--pull', 'never', '--init', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '1g', '--memory-swap', '1g', '--cpus', '1', '--pids-limit', '256', '--shm-size', '256m', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777', '--user', '1000:1000']
        target = '/workspace' if app_command else '/app'
        application = snapshot
        if app_command:
            application = output / 'runtime-state'
            shutil.copytree(snapshot, application, symlinks=True)
            if continuation:
                for name in continuation['paths']:
                    destination = application / name
                    if (destination.is_symlink() or not destination.parent.is_dir()
                            or destination.parent.resolve() != destination.parent
                            or destination.exists() and not destination.is_file()):
                        raise ValueError('continuation target must be a regular file in the disposable application')
                    shutil.copy2(predecessor / name, destination)
                    if hashlib.sha256(destination.read_bytes()).hexdigest() != continuation['files'][name]:
                        raise ValueError('disposable predecessor database copy differs from retained input')
            # A host-owned disposable copy must be writable by the fixed nonroot
            # service UID. Never chmod a link or alter the retained input tree.
            for directory, folders, files in os.walk(application, followlinks=False):
                folder = pathlib.Path(directory)
                mode = stat.S_IMODE(folder.stat().st_mode)
                folder.chmod(mode | ((mode & 0o700) >> 6))
                for filename in files:
                    item = pathlib.Path(directory) / filename
                    if not item.is_symlink():
                        mode = stat.S_IMODE(item.stat().st_mode)
                        item.chmod(mode | ((mode & 0o700) >> 6))
            record['runtime_permissions'] = 'disposable owner permission bits mirrored for nonroot service UID; links untouched; retained input modes unchanged'
            record['runtime_state'] = str(application)
            record['runtime_input_sha256'] = record['snapshot_sha256']
        run(['run', '-d', '--name', names[0], '--network', 'none', *common, '--mount',
             f'type=bind,src={application},dst={target}' + ('' if app_command else ',readonly'), '--workdir', target, args.app_image,
             *(app_command if app_command else ['python', '/app/app.py', args.fixture_variant or args.control])])
        app_started = True
        run(['inspect', names[0]])
        probe = """import json, pathlib, os
root = pathlib.Path('/sys/fs/cgroup')
print(json.dumps(dict(uid=os.getuid(), status=pathlib.Path('/proc/self/status').read_text(), namespaces={n:os.readlink('/proc/self/ns/'+n) for n in ['net','pid','mnt']}, limits={n:(root/n).read_text().strip() for n in ['memory.max','memory.swap.max','pids.max','cpu.max']}, mounts=pathlib.Path('/proc/mounts').read_text(), hidden_visible=pathlib.Path('/oracle/check.cjs').exists(), environment=sorted(os.environ))))"""
        app_probe = json.loads(run(['exec', names[0], 'python', '-I', '-S', '-c', probe]))
        (output / 'application-containment.json').write_text(json.dumps(app_probe, indent=2))
        if app_probe['uid'] != 1000 or app_probe['hidden_visible'] or app_probe['limits'] != {'memory.max':'1073741824','memory.swap.max':'0','pids.max':'256','cpu.max':'100000 100000'}:
            raise ValueError('application containment capability check failed')
        for marker in ('CapEff:\t0000000000000000', 'NoNewPrivs:\t1', 'Seccomp:\t2'):
            if marker not in app_probe['status']:
                raise ValueError('application privilege check failed')

        run(['run', '--name', names[1], '--network', 'container:' + names[0], *common, '--mount', f'type=bind,src={output},dst=/evidence', '--security-opt', 'seccomp=' + str(args.seccomp.resolve()), args.evaluator_image, 'node', '/oracle/check.cjs'])
        run(['inspect', names[1]])
        checks = json.loads((output / 'checks.json').read_text())
        if len(checks['checks']) != len(required) or {c['id'] for c in checks['checks']} != set(required) or any(c['status'] not in ('pass', 'fail', 'unassessable') or c['kind'] != required[c['id']] for c in checks['checks']):
            raise ValueError('missing or invalid required check results')
        for kind in ('functional', 'security'):
            statuses = {check['status'] for check in checks['checks'] if check['kind'] == kind}
            checks[kind] = ('fail' if 'fail' in statuses else
                            'unassessable' if 'unassessable' in statuses else 'pass')
        evaluator_namespaces = checks['diagnostics']['namespaces']
        if app_probe['namespaces']['net'] != evaluator_namespaces['net'] or any(app_probe['namespaces'][n] == evaluator_namespaces[n] for n in ('pid', 'mnt')):
            raise ValueError('application/evaluator namespace separation failed')
        record.update(checks)
        record['outcome'] = ('joint_pass' if checks['functional'] == checks['security'] == 'pass' else
                             'candidate_failure' if 'fail' in (checks['functional'], checks['security']) else 'unassessable')
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        record['error'] = str(error) or 'controller interrupted'
    finally:
        # Repeated operator signals must not interrupt the bounded teardown.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if app_started:
            try:
                run(['logs', names[0]], timeout=20)
                record['application_logs_command'] = len(record['commands'])
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                record.setdefault('diagnostic_errors', []).append(str(error))
        for name in reversed(names):
            try:
                run(['rm', '-f', name], timeout=20)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                record.setdefault('cleanup_errors', []).append(str(error))
        record['resources_removed'] = not bool(record.get('cleanup_errors'))
        if record.get('cleanup_errors'):
            record.update(outcome='evaluator_error', functional='unassessable', security='unassessable')
        record['elapsed_seconds'] = time.monotonic() - start
        write_json(allocation_path, record)
        try:
            record['snapshot_unchanged'] = (digest(snapshot, runtime_image=args.app_image) == record['snapshot_sha256']
                                            if record['snapshot_sha256'] is not None and snapshot.is_dir() else None)
            if predecessor_digest is not None:
                record['predecessor_unchanged'] = digest(predecessor, runtime_image=args.app_image) == predecessor_digest
        except ValueError:
            record['snapshot_unchanged'] = False if record['snapshot_sha256'] is not None else None
            if predecessor_digest is not None:
                record['predecessor_unchanged'] = False
        if record['snapshot_unchanged'] is False or record.get('predecessor_unchanged') is False:
            record.update(outcome='evaluator_error', functional='unassessable', security='unassessable', error='retained snapshot changed during evaluation')
        (output / 'report.md').write_text(f"Outcome: {record['outcome']}\n\nFunctionality: {record['functional']}\nSecurity: {record['security']}\n\n" + '\n'.join(f"- {c['id']}: {c['status']}" for c in record.get('checks', [])) + '\n')
        record['evidence_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
        (output / 'assessment.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({key: record[key] for key in ('functional', 'security')}))

if __name__ == '__main__':
    main()
