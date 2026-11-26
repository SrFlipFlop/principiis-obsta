"""Host-process stand-in for the isolated development runtime; tests only, no model.

The runtime configuration file holds {"argv": [...]}: a local fixture agent that
receives the visible request on stdin inside the checkpoint workspace.
"""
import json
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from principiis.execution import execute  # noqa: E402


class FixtureRuntime:
    def __init__(self, config_path, output, source):
        self.config = json.loads(Path(config_path).read_text())
        self.version = 'fixture-runtime'

    def execute(self, workspace, request, stdout, stderr):
        return execute(self.config['argv'], workspace, request, stdout, stderr)


def develop(sequence, output, step, runtime_config, retry=False, launch_authorization=None):
    from principiis import manual
    args = SimpleNamespace(sequence=str(sequence), output=str(output), step=step,
                           runtime_config=str(runtime_config), retry=retry,
                           launch_authorization=launch_authorization)
    with patch('principiis.development_runtime.DevelopmentRuntime', FixtureRuntime):
        return manual.develop(args)


if __name__ == '__main__':
    # sequence output step runtime-config [--retry]; mirrors the operator's SIGTERM handling.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    develop(*sys.argv[1:5], retry='--retry' in sys.argv[5:])
