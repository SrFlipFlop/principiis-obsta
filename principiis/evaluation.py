"""Restricted, model-free checkpoint assessment. Never launches candidate code on host."""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import os
import stat
import subprocess
import time
import uuid
from .snapshot import validate, inventory
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

    def run(arguments, timeout=120):
        command = docker_command(args.docker, arguments)
        record['commands'].append(command)
        index = len(record['commands'])
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=docker_environment())
        except subprocess.TimeoutExpired as error:
            for stream in ('stdout', 'stderr'):
                data = getattr(error, stream) or b''
                (output / f'{index}.{stream}').write_bytes(data.encode() if isinstance(data, str) else data)
            record.setdefault('exit_statuses', []).append('timeout')
            raise
        except OSError as error:
            (output / f'{index}.stderr').write_text(str(error))
            record.setdefault('exit_statuses', []).append('launch_error')
            raise
        (output / f'{index}.stdout').write_text(result.stdout)
        (output / f'{index}.stderr').write_text(result.stderr)
        record.setdefault('exit_statuses', []).append(result.returncode)
        if result.returncode:
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
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
        record['error'] = str(error)
    finally:
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
        if record.get('cleanup_errors'):
            record.update(outcome='evaluator_error', functional='unassessable', security='unassessable')
        record['elapsed_seconds'] = time.monotonic() - start
        try:
            record['snapshot_unchanged'] = digest(snapshot, runtime_image=args.app_image) == record['snapshot_sha256'] if snapshot.is_dir() else None
        except ValueError:
            record['snapshot_unchanged'] = False if record['snapshot_sha256'] is not None else None
        if record['snapshot_unchanged'] is False:
            record.update(outcome='evaluator_error', functional='unassessable', security='unassessable', error='snapshot changed during evaluation')
        (output / 'report.md').write_text(f"Outcome: {record['outcome']}\n\nFunctionality: {record['functional']}\nSecurity: {record['security']}\n\n" + '\n'.join(f"- {c['id']}: {c['status']}" for c in record.get('checks', [])) + '\n')
        record['evidence_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
        (output / 'assessment.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({key: record[key] for key in ('functional', 'security')}))

if __name__ == '__main__':
    main()
