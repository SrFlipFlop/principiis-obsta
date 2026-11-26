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
