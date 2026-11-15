"""Author-controlled document portal contract release; never supplies a solution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

SOURCE = Path(__file__).resolve().parents[1]
PACKAGE = SOURCE / 'benchmarks/document-portal'


def load_bundle(path, package=PACKAGE):
    raw = (path / 'bundle.json').read_bytes()
    expected = json.loads((package / 'package.json').read_text())['private_bundle_sha256']
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('private bundle metadata digest mismatch')
    bundle = json.loads(raw)
    for name, expected in bundle['files'].items():
        item = (path / name).resolve()
        if not item.is_relative_to(path) or hashlib.sha256(item.read_bytes()).hexdigest() != expected:
            raise ValueError('private bundle content mismatch: ' + name)
    return bundle


def main():
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    release = sub.add_parser('release')
    release.add_argument('--step', type=int, choices=range(1, 11), required=True)
    release.add_argument('--output', type=Path, required=True)
    bind = sub.add_parser('bind')
    bind.add_argument('--bundle', type=Path, required=True)
    bind.add_argument('--output', type=Path, required=True)
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('--bundle', type=Path, required=True)
    evaluate.add_argument('--step', type=int, choices=range(1, 11), required=True)
    evaluate.add_argument('--snapshot', type=Path, default=Path('.'))
    args = parser.parse_args()
    package = PACKAGE
    metadata = json.loads((package / 'package.json').read_text())
    version = metadata.get('version', '1')
    steps = metadata.get('steps', 3)
    if hasattr(args, 'step') and not 1 <= args.step <= steps:
        parser.error('step outside benchmark sequence')
    for name, expected in metadata.get('files', {}).items():
        item = (package / name).resolve()
        if not item.is_relative_to(package.resolve()) or hashlib.sha256(item.read_bytes()).hexdigest() != expected:
            raise ValueError('public package content mismatch: ' + name)
    if args.command == 'release':
        requests = [(package / 'requests' / f'{step:02}.txt').read_text() for step in range(1, args.step + 1)]
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'request.txt').write_text('\n\n'.join(requests))
        return
    root = args.bundle.resolve()
    bundle = load_bundle(root, package)
    if args.command == 'bind':
        manifest = dict(id='document-portal', version=version, condition=dict(id='ordinary', version='1'), steps=[])
        args.output.mkdir(parents=True, exist_ok=False)
        for step in range(1, steps + 1):
            name = f'{step:02}.txt'
            shutil.copyfile(package / 'requests' / name, args.output / name)
            manifest['steps'].append(dict(id=f'portal-{step}', version=version, sequence_version=version, request=name,
                check=[sys.executable, str(Path(__file__).resolve()), 'evaluate', '--bundle', str(root), '--step', str(step)]))
        (args.output / 'sequence.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return
    if (bundle.get('qualification_status') != 'qualified'
            or bundle.get('owner_review') != 'approved'):
        raise ValueError('checker qualification pending or owner review unapproved; qualify and review revised artifacts before evaluation')
    # Stage only candidate source under Docker-visible private storage. Never run it on host.
    snapshot = args.snapshot.resolve()
    from principiis.evaluation import digest
    before = digest(snapshot)
    staged = root / 'runtime' / uuid.uuid4().hex
    staged.parent.mkdir(exist_ok=True)
    shutil.copytree(snapshot, staged)
    try:
        if digest(staged) != before:
            raise ValueError('candidate staging hash mismatch')
        command = [sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(staged), '--output', str(root / 'evidence' / ('assessment-' + uuid.uuid4().hex)),
            '--app-image', bundle['app_image'], '--evaluator-image', bundle['evaluator_images'][str(args.step)], '--version', bundle['version'],
            '--check-contract', str(root / f'step-{args.step}/contract.json'), '--seccomp', str(root / bundle['seccomp'])]
        subprocess.run(command, cwd=SOURCE, check=True)
    finally:
        shutil.rmtree(staged)


if __name__ == '__main__':
    # Direct-file invocation is used by the platform evaluator argv.
    sys.path.insert(0, str(SOURCE))
    main()
