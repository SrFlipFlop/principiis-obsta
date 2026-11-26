"""Shared test helpers."""
from pathlib import Path
import tempfile


def temporary_directory(**kwargs):
    """A TemporaryDirectory whose name is fully resolved.

    The default macOS TMPDIR lives under the /var -> /private/var symlink,
    and production code rejects or resolves symlinked paths.
    """
    kwargs.setdefault('dir', Path(tempfile.gettempdir()).resolve())
    return tempfile.TemporaryDirectory(**kwargs)


ROOT = Path(__file__).resolve().parents[1]
# The public fixture evaluator's check contract and the Node oracle adapter entrypoint.
FIXTURE_CONTRACT = ['--check-contract', str(ROOT / 'fixtures/evaluation/contract.json')]
NODE_ORACLE = ['--evaluator-command', '["node", "/oracle/check.cjs"]']


def create_run(root, *, steps=3, runtime=None, application='document-portal', requests=None, **configuration):
    """A frozen run created through the run store, skipping the operator's package checks."""
    import json
    from principiis.run_store import RunStore
    requests = requests or [f'request {number}' for number in range(1, steps + 1)]
    sequence = {'id': application, 'version': configuration.get('package_version', 'fixture'),
                'condition': {'id': 'baseline', 'version': '1'},
                'steps': [{'id': f'step-{number:02}', 'version': 'fixture', 'sequence_version': 'fixture',
                           'request': f'requests/{number:02}.txt'} for number in range(1, len(requests) + 1)]}
    inputs = {'runtime.json': json.dumps(runtime or {'image': 'sha256:' + 'a' * 64}).encode(),
              'sequence.json': json.dumps(sequence).encode(),
              **{f'requests/{number:02}.txt': text.encode() for number, text in enumerate(requests, 1)}}
    defaults = {'run_name': Path(root).name, 'application': application, 'run_mode': 'development-rehearsal',
                'evaluator_binding': 'unbound', 'investigation': 'none', 'package_version': 'fixture',
                'condition': sequence['condition']}
    return RunStore.create(root, dict(defaults, **configuration), inputs)


# ---- run-store tamper helpers ---------------------------------------------
# Tests outside the run store never parse run JSON. Tamper tests that must
# corrupt a retained record find it here, through the store's own layout.

def development_result(root, step='step-01'):
    """The controller's result file for `step`'s latest development attempt."""
    from principiis.run_store import RunStore
    return RunStore.open(root).attempts_for(step)[-1].directory / 'result.json'


def assessment_result(root, step='step-01', attempt=1):
    """The controller's result file for one retained assessment of `step`."""
    from principiis.run_store import RunStore
    return Path(RunStore.open(root).assessments_for(step)[attempt - 1]['artifact'])


def edit_record(path, **changes):
    """Rewrite a retained JSON record with `changes`, bypassing the store's integrity checks."""
    import json
    path.write_text(json.dumps(dict(json.loads(path.read_text()), **changes)))


EVALUATOR_BINDING = ('evaluator-binding.json', 'evaluator-manifest.json', 'evaluator-release.json')


def remove_evaluator_binding(root):
    """Return a bound run to its never-bound state: no binding and no assessments."""
    import shutil
    shutil.rmtree(Path(root) / 'development/evaluations')
    for name in EVALUATOR_BINDING:
        (Path(root) / name).unlink()


def forge_evaluator_binding(root):
    """Write an evaluator binding the controller never made."""
    (Path(root) / EVALUATOR_BINDING[0]).write_text('{}')


def frozen_input(root, name):
    """A frozen run input such as `runtime.json`, for tests that change it after init."""
    from principiis.run_store import RunStore
    store = RunStore.open(root)
    if name not in store.configuration['frozen_files']:
        raise ValueError('not a frozen run input: ' + name)
    return store.root / name


def runtime_allocation(root, step='step-01'):
    """Where `step`'s latest development attempt keeps its container allocation record."""
    return development_result(root, step).parent / 'runtime.json'


def retain_investigation(root, step, record):
    """Write an AI review record where the reviewer would, without running one."""
    import json
    from principiis.run_store import RunStore
    directory = RunStore.open(root).investigation_directory(step)
    directory.mkdir(parents=True)
    (directory / 'investigation.json').write_text(json.dumps(record))
    return directory


def development_files(root):
    """The run store's digest inventory of development evidence, for immutability checks."""
    from principiis.run_store import RunStore
    return RunStore.open(root).development_files()


def attempt_files(root):
    """The development inventory limited to attempt evidence; the journal grows with every attempt."""
    from principiis.run_store import RunStore
    store = RunStore.open(root)
    directories = [attempt.directory for attempt in store.attempts]
    return {name: entry for name, entry in store.development_files().items()
            if any((store.root / name).is_relative_to(directory) for directory in directories)}
