"""Logging-only network measurement that builds the development allowlist (#75).

    python3 -m principiis.network_measurement --config RUNTIME_JSON --output NEW_DIR

Runs one ordinary Codex development session on a disposable fixture request, with
the egress proxy in `log` mode: every destination is forwarded and recorded. The
output keeps the workspace, Codex logs, `egress.jsonl` and `measurement.json`, whose
`connected_hosts` (destinations that actually answered) are the candidate allowlist. This is a live subscription run; it
needs the owner's approval (AGENTS.md hard rule 3) and never uses a benchmark request.
"""
import argparse
from pathlib import Path

from .development_runtime import CHECKOUT, DevelopmentRuntime
from .jsonio import write_json

REQUEST = CHECKOUT / 'fixtures/development/network_measurement_request.txt'


def measure(config, output, request=REQUEST):
    output = Path(output).resolve()
    runtime = DevelopmentRuntime(config, output, Path(request).resolve().parent, egress='log')
    workspace = output / 'workspace'
    workspace.mkdir(parents=True)
    with (output / 'codex.stdout').open('w') as stdout, (output / 'codex.stderr').open('w') as stderr:
        evidence = runtime.execute(workspace, Path(request).read_text(), stdout, stderr)
    record = {'schema_version': 1, 'request': str(request), 'runtime_version': runtime.version,
              'connected_hosts': evidence['egress']['connected_hosts'],
              'allowed_hosts': evidence['egress']['allowed_hosts'],
              'refused_hosts': evidence['egress']['refused_hosts'], 'execution': evidence}
    write_json(output / 'measurement.json', record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--config', required=True, help='development runtime JSON')
    parser.add_argument('--output', required=True, help='new directory outside the checkout')
    parser.add_argument('--request', default=str(REQUEST), help='disposable fixture request')
    args = parser.parse_args(argv)
    record = measure(args.config, args.output, args.request)
    print('\n'.join(record['connected_hosts']))


if __name__ == '__main__':
    main()
