"""Qualified evaluator binding and the restricted evaluator adapter.

`bind` verifies a private evaluator declaration once, against the public package
that pins its digest, and freezes it into the run. `RestrictedEvaluator` is the
production evaluator for `principiis.pipeline.evaluate`: it runs the bound checks
in separate restricted containers through `principiis.evaluation`.
"""
import json
from pathlib import Path
import re
import sys

from . import benchmark
from .execution import execute
from .jsonio import digest

# Declarations bound before the field existed ran the Node oracle adapter's entrypoint.
NODE_ORACLE_COMMAND = ['node', '/oracle/check.cjs']
REPOSITORY = Path(__file__).resolve().parents[1]


def evaluator_command(manifest):
    command = manifest.get('evaluator_command', NODE_ORACLE_COMMAND)
    if (not isinstance(command, list) or not command
            or not all(isinstance(arg, str) and arg and '\0' not in arg for arg in command)):
        raise ValueError('evaluator command must be a nonempty argv')
    return command


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


def load_declaration(store, declaration_path, package):
    """Verify an author-published qualified bundle against this frozen run."""
    path = Path(declaration_path).resolve()
    metadata_path = package / 'package.json'
    metadata = json.loads(metadata_path.read_text())
    sequence = store.sequence
    benchmark.check_sequence(metadata, sequence)
    if digest(path) != metadata['private_bundle_sha256']:
        raise ValueError('evaluator declaration differs from the qualified public release')
    manifest = json.loads(path.read_text())
    if (not isinstance(manifest, dict) or not isinstance(manifest.get('version'), str)
            or not manifest['version'].strip() or manifest.get('complete') is not True):
        raise ValueError('complete qualified evaluator declaration required')
    evaluator_command(manifest)
    if metadata.get('id') != store.configuration.get('application'):
        raise ValueError('evaluator application differs from the frozen run')
    if metadata.get('version') != store.configuration.get('package_version'):
        raise ValueError('evaluator request package version differs; use a new run')
    # The store verified these frozen request digests when it opened.
    frozen = store.configuration['frozen_files']
    expected_requests = {step['request']: frozen[step['request']] for step in sequence['steps']}
    if manifest.get('requests') != expected_requests:
        raise ValueError('evaluator requests differ from the frozen development requests')
    for name, expected in expected_requests.items():
        if metadata.get('files', {}).get(name) != expected or digest(_relative(package, name)) != expected:
            raise ValueError('qualified public request differs from the frozen development request')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('complete evaluator dependency files are required')
    for name, expected in files.items():
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected) or digest(_relative(path.parent, name)) != expected:
            raise ValueError('evaluator dependency content changed: ' + str(name))

    def dependency(name):
        if name not in files:
            raise ValueError('evaluator dependency absent from complete manifest: ' + str(name))
        return _relative(path.parent, name)
    image = manifest.get('runtime_image')
    image_pattern = r'sha256:[0-9a-f]{64}'
    if not isinstance(image, str) or not re.fullmatch(image_pattern, image):
        raise ValueError('pinned candidate runtime image required')
    if store.frozen('runtime.json').get('image') != image:
        raise ValueError('candidate runtime differs from the retained development image')
    ids = set(store.step_ids)
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
            'manifest_sha256': digest(path), 'files': files, 'declaration': manifest,
            'package_sha256': digest(metadata_path)}


def bind(store, declaration_path, package=None):
    """Verify and freeze a qualified evaluator into the run; `package` defaults to the application's."""
    package = Path(package) if package else benchmark.directory(store.configuration.get('application'))
    binding = load_declaration(store, declaration_path, package)
    store.bind(binding, declaration_path, package / 'package.json')
    return store.binding


class RestrictedEvaluator:
    """Runs a bound step's hidden checks in separate restricted containers."""

    def __init__(self, binding, docker):
        self.binding, self.docker = binding, docker
        self.manifest = binding['declaration']
        self.directory = Path(binding['manifest']).parent

    def _file(self, name):
        path = _relative(self.directory, name)
        if digest(path) != self.binding['files'].get(name):
            raise ValueError('evaluator dependency content changed: ' + str(name))
        return path

    def verify(self, step):
        """The files this step uses still match the binding."""
        self._file(self.manifest['steps'][step]['contract'])
        self._file(self.manifest['seccomp'])

    def coverage(self, step):
        return _contract(self._file(self.manifest['steps'][step]['contract']))

    def run(self, candidate, output, step, stdout, stderr):
        settings = self.manifest['steps'][step]
        command = [sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(candidate),
                   '--output', str(output), '--app-image', self.manifest['runtime_image'],
                   '--evaluator-image', self.manifest['evaluator_images'][step], '--version', self.binding['version'],
                   '--check-contract', str(self._file(settings['contract'])),
                   '--evaluator-command', json.dumps(evaluator_command(self.manifest)),
                   '--seccomp', str(self._file(self.manifest['seccomp'])),
                   '--app-command', json.dumps(settings['app_command']), '--docker', self.docker]
        return execute(command, REPOSITORY, '', stdout, stderr, termination_grace_seconds=75)
