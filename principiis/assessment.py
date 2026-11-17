"""Explicit qualified evaluator binding, separate from retained development identity."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import sys
import uuid

from .execution import execute
from .manual import _journal_attempts
from .snapshot import validate

from . import resource
from .resume import write_json

PACKAGE = Path(__file__).resolve().parents[1] / 'benchmarks/document-portal'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _relative(directory, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError('evaluator dependency must be a relative file')
    path = directory / name
    if '..' in Path(name).parts or path.resolve() != path or not path.is_file():
        raise ValueError('evaluator dependency must be a regular file within its directory')
    return path


def _contract(path):
    contract = json.loads(path.read_text())
    if (not isinstance(contract, dict) or not contract
            or not all(isinstance(key, str) and key and kind in ('functional', 'security')
                       for key, kind in contract.items())
            or set(contract.values()) != {'functional', 'security'}):
        raise ValueError('both functional and security check contracts are required')
    return contract


def load_declaration(root, configuration, declaration_path, *, frozen_release=None):
    """Verify an author-published qualified bundle against this frozen run."""
    root = Path(root).resolve()
    path = Path(declaration_path).resolve()
    metadata_path = Path(frozen_release) if frozen_release else PACKAGE / 'package.json'
    metadata = json.loads(metadata_path.read_text())
    if (metadata.get('qualification_status') != 'qualified'
            or metadata.get('owner_review') != 'approved'
            or not metadata.get('private_bundle_sha256')):
        raise ValueError('a qualified, owner-approved portal release with a bound evaluator is required')
    if sha(path) != metadata['private_bundle_sha256']:
        raise ValueError('evaluator declaration differs from the qualified public release')
    manifest = json.loads(path.read_text())
    if (not isinstance(manifest, dict) or not isinstance(manifest.get('version'), str)
            or not manifest['version'].strip() or manifest.get('complete') is not True
            or manifest.get('qualification_status') != 'qualified' or manifest.get('owner_review') != 'approved'):
        raise ValueError('complete qualified and approved evaluator declaration required')
    if configuration.get('application') != 'document-portal' or metadata.get('id') != 'document-portal':
        raise ValueError('portal evaluator requires a portal run')
    if metadata.get('version') != configuration.get('package_version'):
        raise ValueError('evaluator request package version differs; use a new run')
    for name, expected in configuration['frozen_files'].items():
        if sha(_relative(root, name)) != expected:
            raise ValueError('frozen development configuration changed; use a new run')
    sequence = json.loads((root / 'sequence.json').read_text())
    expected_requests = {step['request']: sha(_relative(root, step['request'])) for step in sequence['steps']}
    if manifest.get('requests') != expected_requests:
        raise ValueError('evaluator requests differ from the frozen development requests')
    for name, expected in expected_requests.items():
        if metadata.get('files', {}).get(name) != expected or sha(_relative(root if frozen_release else PACKAGE, name)) != expected:
            raise ValueError('qualified public request differs from the frozen development request')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('complete evaluator dependency files are required')
    for name, expected in files.items():
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected) or sha(_relative(path.parent, name)) != expected:
            raise ValueError('evaluator dependency content changed: ' + str(name))
    def dependency(name):
        if name not in files:
            raise ValueError('evaluator dependency absent from complete manifest: ' + str(name))
        return _relative(path.parent, name)
    image = manifest.get('runtime_image')
    image_pattern = r'sha256:[0-9a-f]{64}'
    if not isinstance(image, str) or not re.fullmatch(image_pattern, image):
        raise ValueError('pinned candidate runtime image required')
    runtime = json.loads((root / 'runtime.json').read_text())
    if runtime.get('image') != image:
        raise ValueError('candidate runtime differs from the retained development image')
    ids = {step['id'] for step in sequence['steps']}
    images, steps = manifest.get('evaluator_images'), manifest.get('steps')
    if not isinstance(images, dict) or set(images) != ids or not all(isinstance(value, str) and re.fullmatch(image_pattern, value) for value in images.values()):
        raise ValueError('pinned evaluator images for every frozen checkpoint are required')
    if not isinstance(steps, dict) or set(steps) != ids:
        raise ValueError('matching cumulative checks for every frozen checkpoint are required')
    for step in steps.values():
        if not isinstance(step, dict):
            raise ValueError('invalid evaluator step declaration')
        _contract(dependency(step.get('contract')))
        command = step.get('app_command')
        if (not isinstance(command, list) or not command
                or not all(isinstance(arg, str) and arg and '\0' not in arg for arg in command)):
            raise ValueError('explicit candidate startup argv required')
    dependency(manifest.get('seccomp'))
    dependencies = json.loads(dependency(manifest.get('dependency_manifest')).read_text())
    if (not isinstance(dependencies, dict) or dependencies.get('complete') is not True
            or not isinstance(dependencies.get('images'), dict)
            or set(dependencies['images']) != {image, *images.values()}):
        raise ValueError('complete dependency inventory for every runtime image is required')
    for inventory in dependencies['images'].values():
        packages = inventory.get('packages') if isinstance(inventory, dict) else None
        if (not isinstance(packages, list) or not packages
                or not all(isinstance(package, dict) and isinstance(package.get('name'), str)
                           and package['name'] and isinstance(package.get('version'), str)
                           and package['version'] for package in packages)):
            raise ValueError('resolved package names and versions are required')
        receipts = inventory.get('preparation_evidence')
        if not isinstance(receipts, list) or not receipts:
            raise ValueError('dependency preparation evidence is required')
        for receipt in receipts:
            dependency(receipt)
    return {'schema_version': 1, 'version': manifest['version'], 'manifest': str(path),
            'manifest_sha256': sha(path), 'files': files, 'declaration': manifest,
            'package_sha256': sha(metadata_path),
            'development_configuration_sha256': sha(root / 'configuration.json')}


def bind(root, configuration, declaration_path):
    root = Path(root).resolve()
    binding = load_declaration(root, configuration, declaration_path)
    target = root / 'evaluator-binding.json'
    if target.is_symlink():
        raise ValueError('evaluator binding cannot be a symlink')
    if target.exists():
        if json.loads(target.read_text()) != binding:
            raise ValueError('evaluator binding changed; preserve this run and use a new run')
    else:
        (root / 'evaluator-manifest.json').write_bytes(Path(declaration_path).read_bytes())
        (root / 'evaluator-release.json').write_bytes((PACKAGE / 'package.json').read_bytes())
        write_json(target, binding)
    return binding


def _binding(root, configuration):
    path = root / 'evaluator-binding.json'
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError('evaluator binding cannot be a symlink')
    binding = json.loads(path.read_text())
    frozen = root / 'evaluator-manifest.json'
    release = root / 'evaluator-release.json'
    if (frozen.is_symlink() or release.is_symlink()
            or sha(frozen) != binding['manifest_sha256'] or sha(release) != binding['package_sha256']
            or json.loads(frozen.read_text()) != binding['declaration']
            or binding['files'] != binding['declaration']['files']
            or binding['version'] != binding['declaration']['version']
            or sha(root / 'configuration.json') != binding['development_configuration_sha256']):
        raise ValueError('retained evaluator binding changed')
    return binding


def _assessments(root, binding):
    sequence = json.loads((root / 'sequence.json').read_text())
    records = []
    state_path = root / 'development/manual.json'
    state = json.loads(state_path.read_text()) if state_path.is_file() else None
    completed = {}
    if state is not None:
        attempts, _ = _journal_attempts(root / 'development', state, [item['id'] for item in sequence['steps']])
        completed = {entry['id']: directory for entry, directory, result in attempts
                     if result and result.get('completed') is True}
    for step in sequence['steps']:
        parent = root / 'development/evaluations' / step['id']
        ledger = parent / 'allocations.json'
        if not ledger.exists():
            if parent.exists():
                raise ValueError('assessment directory has no canonical allocation ledger')
            continue
        if parent.resolve() != parent or ledger.is_symlink():
            raise ValueError('assessment ledger cannot be a symlink')
        allocations = json.loads(ledger.read_text())
        if not isinstance(allocations, list):
            raise ValueError('invalid assessment ledger')
        for index, allocation in enumerate(allocations, 1):
            if (not isinstance(allocation, dict) or allocation.get('attempt') != index
                    or allocation.get('checkpoint') != step['id']
                    or allocation.get('role') != ('primary' if index == 1 else 'rerun')
                    or allocation.get('stage') != 'independent_evaluation'
                    or allocation.get('binding_sha256') != binding['manifest_sha256']):
                raise ValueError('invalid canonical assessment allocation')
            path = parent / str(index) / 'result.json'
            if path.resolve() != path:
                raise ValueError('assessment result cannot be a symlink')
            result = json.loads(path.read_text()) if path.is_file() else dict(allocation,
                error='controller interrupted after allocation; measurements unavailable')
            for key in ('run_id', 'session_id', 'checkpoint', 'attempt', 'role', 'binding_sha256',
                        'developer_result_sha256', 'snapshot_manifest_sha256'):
                if result.get(key) != allocation.get(key):
                    raise ValueError('assessment result differs from canonical allocation')
            checkpoint = completed.get(step['id'])
            if (checkpoint is None or result.get('run_id') != state['run_id']
                    or result.get('developer_result_sha256') != sha(checkpoint / 'result.json')
                    or result.get('snapshot_manifest_sha256') != sha(checkpoint / 'snapshot.json')
                    or result.get('snapshot') != str(checkpoint / 'snapshot')):
                raise ValueError('assessment identity differs from completed development checkpoint')
            records.append(dict(result, artifact=str(path)))
    identities = [result['session_id'] for result in records]
    if len(set(identities)) != len(identities):
        raise ValueError('duplicate assessment session identity')
    return records


def inspect(root, configuration):
    """Read canonical allocations only; candidate-owned files cannot add results."""
    root = Path(root).resolve()
    binding = _binding(root, configuration)
    if not binding and (root / 'development/evaluations').exists():
        raise ValueError('retained assessments exist without their evaluator binding')
    assessments = _assessments(root, binding) if binding else []
    attempts = [{'run_id': result['run_id'], 'session_id': result['session_id'],
                 'checkpoint': result['checkpoint'], 'attempt': result['attempt'],
                 'outcome': result['outcome'], 'artifact': result['artifact'],
                 'stages': {'development': {}, 'evaluation': dict(result['evaluation'], tokens=None)}}
                for result in assessments]
    from .evaluation_cleanup import pending
    return {'binding': binding, 'assessments': assessments, 'resources': resource.summarize(attempts),
            'cleanup_required': pending(root, assessments)}


def evaluate(root, configuration, step, *, rerun=False, authorization=None):
    """Execute one restricted primary assessment or an explicit retained rerun."""
    root = Path(root).resolve()
    evidence = inspect(root, configuration)
    binding = evidence['binding']
    if binding is None:
        raise ValueError('development rehearsal evaluator is unbound; bind a qualified evaluator first')
    if evidence['cleanup_required']:
        raise ValueError('retained evaluation runtime requires explicit cleanup before another assessment')
    if load_declaration(root, configuration, binding['manifest'],
                        frozen_release=root / 'evaluator-release.json') != binding:
        raise ValueError('retained evaluator binding changed')
    manifest = binding['declaration']
    if step not in manifest['steps']:
        raise ValueError('checkpoint is outside the frozen evaluator binding')
    previous = [result for result in evidence['assessments'] if result['checkpoint'] == step]
    if previous and not rerun:
        raise ValueError('primary assessment retained; explicit --rerun required')
    if not previous and rerun:
        raise ValueError('no primary assessment to rerun')
    development = root / 'development'
    state = json.loads((development / 'manual.json').read_text())
    sequence = json.loads((root / 'sequence.json').read_text())
    attempts, _ = _journal_attempts(development, state, [item['id'] for item in sequence['steps']])
    completed = [directory for record, directory, result in attempts
                 if record['id'] == step and result and result.get('completed') is True]
    if not completed:
        raise ValueError('completed developer checkpoint required')
    checkpoint = completed[-1]
    snapshot = checkpoint / 'snapshot'
    validate(snapshot, runtime_image=manifest['runtime_image'])
    number = len(previous) + 1
    parent = development / 'evaluations' / step
    output = parent / str(number)
    result = {'schema_version': 1, 'stage': 'independent_evaluation', 'run_id': state['run_id'],
              'session_id': str(uuid.uuid4()), 'checkpoint': step, 'attempt': number,
              'role': 'primary' if number == 1 else 'rerun', 'binding_sha256': binding['manifest_sha256'],
              'provenance': binding, 'developer_result_sha256': sha(checkpoint / 'result.json'),
              'snapshot': str(snapshot), 'snapshot_manifest_sha256': sha(snapshot.with_suffix('.json')),
              'outcome': 'evaluator_error', 'functional': 'unassessable', 'security': 'unassessable',
              'evaluation': {}, 'authorization': authorization, 'cleanup_pending': True, 'evidence': str(output / 'restricted/assessment.json')}
    parent.mkdir(parents=True, exist_ok=True)
    ledger_path = parent / 'allocations.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    ledger.append(result)
    write_json(ledger_path, ledger)
    output.mkdir(exist_ok=False)
    write_json(output / 'result.json', result)
    runtime_launch_attempted = False
    try:
        candidate = output / 'input'
        shutil.copytree(snapshot, candidate, symlinks=True)
        shutil.copyfile(snapshot.with_suffix('.json'), candidate.with_suffix('.json'))
        validate(candidate, runtime_image=manifest['runtime_image'])
        declaration = Path(binding['manifest']).parent
        runtime = json.loads((root / 'runtime.json').read_text())
        settings = manifest['steps'][step]
        command = [sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(candidate),
                   '--output', str(output / 'restricted'), '--app-image', manifest['runtime_image'],
                   '--evaluator-image', manifest['evaluator_images'][step], '--version', binding['version'],
                   '--check-contract', str(declaration / settings['contract']),
                   '--seccomp', str(declaration / manifest['seccomp']),
                   '--app-command', json.dumps(settings['app_command']), '--docker', runtime.get('docker', 'docker')]
        result['python_executable'] = {'path': sys.executable, 'sha256': sha(sys.executable)}
        result['controller_sources'] = {name: sha(Path(__file__).parent / name)
                                       for name in ('assessment.py', 'evaluation.py', 'execution.py', 'snapshot.py')}
        with (output / 'evaluator.stdout').open('w') as stdout, (output / 'evaluator.stderr').open('w') as stderr:
            runtime_launch_attempted = True
            result['evaluation'] = dict(execute(command, Path(__file__).resolve().parents[1], '', stdout, stderr,
                                                      termination_grace_seconds=75), tokens=None)
        if result['evaluation']['exit_status'] != 0:
            raise ValueError('restricted evaluator exited unsuccessfully')
        observed = json.loads(Path(result['evidence']).read_text())
        if observed.get('outcome') not in ('joint_pass', 'candidate_failure', 'unassessable', 'evaluator_error'):
            raise ValueError('invalid restricted evaluator outcome')
        for key in ('outcome', 'functional', 'security', 'checks', 'error', 'evidence_sha256'):
            if key in observed:
                result[key] = observed[key]
        result['coverage'] = _contract(declaration / settings['contract'])
        result['evaluation']['runtime_elapsed_seconds'] = observed.get('elapsed_seconds')
    except (OSError, ValueError, TypeError, KeyError, KeyboardInterrupt) as error:
        result.update(outcome='evaluator_error', functional='unassessable', security='unassessable',
                      error=str(error) or 'controller interrupted')
    finally:
        runtime_allocation = output / 'restricted/runtime-allocation.json'
        result['runtime_launch_attempted'] = runtime_launch_attempted
        result['cleanup_pending'] = runtime_launch_attempted
        try:
            if runtime_allocation.is_file():
                allocation = json.loads(runtime_allocation.read_text())
                result['runtime_allocation'] = str(runtime_allocation)
                result['containers'] = allocation.get('containers')
                result['cleanup_argv'] = allocation.get('cleanup_argv')
                result['cleanup_pending'] = allocation.get('resources_removed') is not True
        except (OSError, ValueError, TypeError, AttributeError) as error:
            result['cleanup_evidence_error'] = str(error)
        if result.get('evaluation', {}).get('termination', {}).get('forced'):
            result['cleanup_pending'] = True
        if result['cleanup_pending']:
            result.update(outcome='evaluator_error', functional='unassessable', security='unassessable')
            result.setdefault('error', 'runtime cleanup remains unresolved')
        try:
            validate(snapshot, runtime_image=manifest['runtime_image'])
            if sha(checkpoint / 'result.json') != result['developer_result_sha256']:
                raise ValueError('development result changed during evaluation')
            result['snapshot_unchanged'] = True
        except (OSError, ValueError) as error:
            result.update(snapshot_unchanged=False, outcome='evaluator_error', functional='unassessable',
                          security='unassessable', error=str(error))
        write_json(output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('bind')
    command.add_argument('--root', type=Path, required=True)
    command.add_argument('--declaration', type=Path, required=True)
    ev = sub.add_parser('evaluate')
    ev.add_argument('--root', type=Path, required=True)
    ev.add_argument('--step', required=True)
    ev.add_argument('--rerun', action='store_true')
    view = sub.add_parser('inspect')
    view.add_argument('--root', type=Path, required=True)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        configuration = json.loads((root / 'configuration.json').read_text())
        result = (bind(root, configuration, args.declaration) if args.command == 'bind' else
                  inspect(root, configuration) if args.command == 'inspect' else
                  evaluate(root, configuration, args.step, rerun=args.rerun))
        print(json.dumps(result))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
