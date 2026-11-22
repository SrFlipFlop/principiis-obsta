"""Frozen, explicitly supported development condition definitions."""
import json
from pathlib import Path
import re


DEFINITIONS = Path(__file__).with_name('experiment_definitions')


def load(name):
    if not re.fullmatch(r'[a-z][a-z0-9-]*', name):
        raise ValueError('condition name must use lowercase letters, numbers and hyphens')
    path = DEFINITIONS / (name + '.json')
    if not path.is_file():
        raise ValueError(f'condition {name!r} is not implemented')
    definition = json.loads(path.read_text())
    if set(definition) != {'id', 'version', 'kind'} or definition['id'] != name or not isinstance(definition['version'], str):
        raise ValueError('invalid condition definition')
    if definition['kind'] != 'ordinary':
        raise ValueError(f'condition {name!r} requires an implemented intervention adapter')
    if name != 'baseline':
        raise ValueError(f'condition {name!r} has no qualified intervention implementation')
    return path, definition
