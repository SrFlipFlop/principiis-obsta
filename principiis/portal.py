"""Author-controlled document portal request release; never supplies a solution."""
import argparse
import hashlib
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
PACKAGE = SOURCE / 'benchmarks/document-portal'


def main():
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    release = sub.add_parser('release')
    release.add_argument('--step', type=int, choices=range(1, 11), required=True)
    release.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package = PACKAGE
    metadata = json.loads((package / 'package.json').read_text())
    if not 1 <= args.step <= metadata.get('steps', 3):
        parser.error('step outside benchmark sequence')
    for name, expected in metadata.get('files', {}).items():
        item = (package / name).resolve()
        if not item.is_relative_to(package.resolve()) or hashlib.sha256(item.read_bytes()).hexdigest() != expected:
            raise ValueError('public package content mismatch: ' + name)
    requests = [(package / 'requests' / f'{step:02}.txt').read_text() for step in range(1, args.step + 1)]
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'request.txt').write_text('\n\n'.join(requests))


if __name__ == '__main__':
    main()
