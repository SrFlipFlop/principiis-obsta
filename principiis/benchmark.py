"""Benchmark application packages: public requests, their hashes and the pinned private evaluator.

Each application is a `benchmarks/<app>/package.json` plus the files it hashes. No
application is known to code: adding one needs only its directory and a private
evaluator declaration whose SHA-256 the package pins as `private_bundle_sha256`.
`qualified_through` is the last step whose evaluator passed its controls (ADR 0002).
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

BENCHMARKS = Path(__file__).resolve().parents[1] / 'benchmarks'
_NAME = re.compile(r'[a-z][a-z0-9-]*')
_DIGEST = re.compile(r'[0-9a-f]{64}')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def step_id(number):
    return f'step-{number:02}'


def request_name(number):
    return f'requests/{number:02}.txt'


def applications():
    """Every application directory under `benchmarks/` that publishes a package."""
    return sorted(path.name for path in BENCHMARKS.iterdir()
                  if _NAME.fullmatch(path.name) and (path / 'package.json').is_file())


def directory(application):
    if not isinstance(application, str) or not _NAME.fullmatch(application):
        raise ValueError('invalid application identity')
    return BENCHMARKS / application


def qualified_through(metadata):
    """The last step with a qualified evaluator; zero means none is usable."""
    value = metadata.get('qualified_through', 0)
    if type(value) is not int or value < 0:
        raise ValueError('qualified_through must be a nonnegative step number')
    if value and not _DIGEST.fullmatch(str(metadata.get('private_bundle_sha256'))):
        raise ValueError('a qualified package requires its private evaluator bundle digest')
    return value


def check_sequence(metadata, sequence):
    """A frozen run sequence must be the package's first steps, all within its qualified range."""
    steps = sequence['steps']
    expected = [(step_id(number), request_name(number)) for number in range(1, len(steps) + 1)]
    if [(step.get('id'), step.get('request')) for step in steps] != expected:
        raise ValueError('frozen sequence is not a prefix of the application requests')
    if not steps or len(steps) > qualified_through(metadata):
        raise ValueError('a qualified application release with a bound evaluator is required '
                         f'for {len(steps)} steps; the evaluator is qualified through step '
                         f'{qualified_through(metadata)}')


def load(application):
    """Read and verify a package: identity, step range and every hashed file."""
    package = directory(application)
    path = package / 'package.json'
    if path.is_symlink() or not path.is_file():
        raise ValueError('unknown application: ' + application)
    metadata = json.loads(path.read_text())
    if metadata.get('id') != application or not isinstance(metadata.get('version'), str) or not metadata['version'].strip():
        raise ValueError('package requires a matching application identity and version')
    steps = metadata.get('steps')
    if type(steps) is not int or steps < 1:
        raise ValueError('package must declare its number of steps')
    if qualified_through(metadata) > steps:
        raise ValueError('package cannot be qualified beyond its last step')
    files = metadata.get('files')
    requests = {request_name(number) for number in range(1, steps + 1)}
    if not isinstance(files, dict) or not requests.issubset(files):
        raise ValueError('package manifest must cover every request')
    for name, expected in files.items():
        relative = Path(name)
        item = package / relative
        if (relative.is_absolute() or '..' in relative.parts or not item.is_file()
                or any(parent.is_symlink() for parent in (item, *item.parents)
                       if parent != package and parent.is_relative_to(package))):
            raise ValueError('package manifest paths must be regular files within the package')
        if not isinstance(expected, str) or not _DIGEST.fullmatch(expected):
            raise ValueError('package manifest requires SHA-256 digests')
        if sha(item) != expected:
            raise ValueError('package content mismatch: ' + name)
        if name in requests and not item.read_text().strip():
            raise ValueError('package requests must be nonempty UTF-8 text')
    return metadata


def requests(application, metadata, count):
    """The first `count` verified request files, as (relative name, bytes)."""
    package = directory(application)
    if not 1 <= count <= metadata['steps']:
        raise ValueError(f'select steps 1 through {metadata["steps"]}')
    released = []
    for number in range(1, count + 1):
        name = request_name(number)
        content = (package / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != metadata['files'][name]:
            raise ValueError('package content mismatch: ' + name)
        released.append((name, content))
    return released


def release(application, step, output):
    """Author tool: write the cumulative request text a developer sees at `step`."""
    metadata = load(application)
    text = '\n\n'.join(content.decode() for _, content in requests(application, metadata, step))
    Path(output).mkdir(parents=True, exist_ok=False)
    (Path(output) / 'request.txt').write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('release', help='write the cumulative requests through one step')
    command.add_argument('--application', required=True)
    command.add_argument('--step', type=int, required=True)
    command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        release(args.application, args.step, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
