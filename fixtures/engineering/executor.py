"""Trusted deterministic executor double; never calls a model."""
from pathlib import Path
import sys

request = sys.stdin.read()
assert request == 'Create answer.txt containing exactly hello followed by a newline. Do not create any other files.\n'
assert not list(Path.cwd().iterdir()), 'initial project must be empty'
Path('answer.txt').write_text('hello\n' if sys.argv[1] == 'pass' else 'wrong\n')

if sys.argv[1] == 'evaluator-error':
    Path('oracle-error').write_text('trigger evaluator error')

if sys.argv[1] == 'incomplete':
    sys.exit(7)

if sys.argv[1] == 'malformed':
    Path('malformed').write_text('trigger malformed scores')
