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
