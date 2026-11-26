"""Host-process stand-in for the isolated development runtime; tests only, no model.

The runtime configuration file holds {"argv": [...]}: a local fixture agent that
receives the visible request on stdin inside the checkpoint workspace.
"""
import json
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from principiis import pipeline  # noqa: E402
from principiis.execution import execute  # noqa: E402
from principiis.run_store import RunStore  # noqa: E402


class FixtureRuntime:
    def __init__(self, config_path):
        self.config = json.loads(Path(config_path).read_text())

    def execute(self, workspace, request, stdout, stderr):
        return execute(self.config['argv'], workspace, request, stdout, stderr)


def develop(run, step, runtime_config, retry=False):
    return pipeline.develop(RunStore.open(run), step, retry=retry, runtime=FixtureRuntime(runtime_config))


if __name__ == '__main__':
    # run step runtime-config [--retry]; mirrors the operator's SIGTERM handling.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    develop(*sys.argv[1:4], retry='--retry' in sys.argv[4:])
