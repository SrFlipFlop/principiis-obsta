"""Restricted, model-free checkpoint assessment. Never launches candidate code on host."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import time
import uuid
from .snapshot import validate


def digest(path):
    if not path.is_dir():
        raise ValueError('snapshot must be an existing directory')
    if path.with_suffix('.json').exists():
        validate(path)
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
    parser.add_argument('--evaluator-image', required=True)
    parser.add_argument('--version', default='engineering-1')
    parser.add_argument('--control', choices=['safe', 'ui-only', 'reject-all', 'alternative'], default='safe')
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

    def run(arguments, timeout=120):
        command = [args.docker, *arguments]
        record['commands'].append(command)
        index = len(record['commands'])
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
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
        record['snapshot_sha256'] = digest(snapshot)
        record['evaluator_image'] = args.evaluator_image
        record['app_image'] = args.app_image
        record['seccomp_sha256'] = hashlib.sha256(args.seccomp.read_bytes()).hexdigest()
        for image in [args.app_image, args.evaluator_image]:
            if not image.startswith('sha256:'):
                raise ValueError('prepared images must be pinned by local sha256 image ID')
            run(['image', 'inspect', image])
        common = ['--pull', 'never', '--init', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--memory', '1g', '--memory-swap', '1g', '--cpus', '1', '--pids-limit', '256', '--shm-size', '256m', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777', '--user', '1000:1000']
        run(['run', '-d', '--name', names[0], '--network', 'none', *common, '--mount', f'type=bind,src={snapshot},dst=/app,readonly', args.app_image, 'python', '/app/app.py', args.control])
        run(['inspect', names[0]])
        probe = """import json, pathlib, os
root = pathlib.Path('/sys/fs/cgroup')
print(json.dumps(dict(uid=os.getuid(), status=pathlib.Path('/proc/self/status').read_text(), namespaces={n:os.readlink('/proc/self/ns/'+n) for n in ['net','pid','mnt']}, limits={n:(root/n).read_text().strip() for n in ['memory.max','memory.swap.max','pids.max','cpu.max']}, mounts=pathlib.Path('/proc/mounts').read_text(), hidden_visible=pathlib.Path('/oracle/check.cjs').exists(), environment=sorted(os.environ))))"""
        app_probe = json.loads(run(['exec', names[0], 'python', '-c', probe]))
        (output / 'application-containment.json').write_text(json.dumps(app_probe, indent=2))
        if app_probe['uid'] != 1000 or app_probe['hidden_visible'] or app_probe['limits'] != {'memory.max':'1073741824','memory.swap.max':'0','pids.max':'256','cpu.max':'100000 100000'}:
            raise ValueError('application containment capability check failed')
        for marker in ('CapEff:\t0000000000000000', 'NoNewPrivs:\t1', 'Seccomp:\t2'):
            if marker not in app_probe['status']:
                raise ValueError('application privilege check failed')

        run(['run', '--name', names[1], '--network', 'container:' + names[0], *common, '--mount', f'type=bind,src={output},dst=/evidence', '--security-opt', 'seccomp=' + str(args.seccomp.resolve()), args.evaluator_image, 'node', '/oracle/check.cjs'])
        run(['inspect', names[1]])
        checks = json.loads((output / 'checks.json').read_text())
        required = {name: kind for kind, names in [('functional', ['browser-own-read', 'api-own-read', 'api-own-update', 'integration-audit']), ('security', ['backend-cross-user-read', 'backend-cross-user-update'])] for name in names}
        if len(checks['checks']) != len(required) or {c['id'] for c in checks['checks']} != set(required) or any(c['status'] not in ('pass', 'fail') or c['kind'] != required[c['id']] for c in checks['checks']):
            raise ValueError('missing or invalid required check results')
        for kind in ('functional', 'security'):
            checks[kind] = 'pass' if all(c['status'] == 'pass' for c in checks['checks'] if c['kind'] == kind) else 'fail'
        evaluator_namespaces = checks['diagnostics']['namespaces']
        if app_probe['namespaces']['net'] != evaluator_namespaces['net'] or any(app_probe['namespaces'][n] == evaluator_namespaces[n] for n in ('pid', 'mnt')):
            raise ValueError('application/evaluator namespace separation failed')
        record.update(checks)
        record['outcome'] = 'joint_pass' if checks['functional'] == checks['security'] == 'pass' else 'candidate_failure'
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
        record['error'] = str(error)
    finally:
        for name in reversed(names):
            try:
                run(['rm', '-f', name], timeout=20)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                record.setdefault('cleanup_errors', []).append(str(error))
        if record.get('cleanup_errors'):
            record.update(outcome='evaluator_error', functional='unassessable', security='unassessable')
        record['elapsed_seconds'] = time.monotonic() - start
        try:
            record['snapshot_unchanged'] = digest(snapshot) == record['snapshot_sha256'] if snapshot.is_dir() else None
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
