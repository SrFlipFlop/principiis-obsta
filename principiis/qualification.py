"""Public package prerequisites for a frozen ten-checkpoint qualification run."""
import hashlib
import json
from pathlib import Path
import re


def load_qualified_package(package, *, expected_steps=10):
    """Validate the public declaration; private evaluator binding is still required.

    This gate never executes candidate code, an evaluator or a model. A declaration
    of qualification is not itself new oracle or live-acceptance evidence.
    """
    package = Path(package).resolve()
    path = package / 'package.json'
    if path.is_symlink():
        raise ValueError('qualified package metadata cannot be a symlink')
    metadata = json.loads(path.read_text())
    if metadata.get('qualification_status') != 'qualified':
        raise ValueError('ten-step run requires a qualified portal package from #9; qualification remains pending')
    if metadata.get('owner_review') != 'approved':
        raise ValueError('ten-step package owner review from #9 must be approved before qualification')
    if metadata.get('id') != 'document-portal' or not isinstance(metadata.get('version'), str) or not metadata['version'].strip():
        raise ValueError('qualified package requires a document-portal identity and version')
    if type(metadata.get('steps')) is not int or metadata['steps'] != expected_steps:
        raise ValueError('qualified package must contain exactly ten steps')
    if not isinstance(metadata.get('private_bundle_sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', metadata['private_bundle_sha256']):
        raise ValueError('qualified package requires a frozen private evaluator bundle digest from #9')
    files = metadata.get('files')
    if not isinstance(files, dict):
        raise ValueError('qualified package requires a complete file manifest')
    required = {f'requests/{number:02}.txt' for number in range(1, expected_steps + 1)}
    if not required.issubset(files):
        raise ValueError('qualified package manifest must cover all ten requests')
    for name, expected in files.items():
        relative = Path(name)
        item = package / relative
        if relative.is_absolute() or '..' in relative.parts or any(parent.is_symlink() for parent in (item, *item.parents) if parent != package and parent.is_relative_to(package)):
            raise ValueError('qualified package manifest paths must be regular files within the package')
        if not item.is_file() or not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError('qualified package manifest requires regular files and SHA-256 digests')
        if name in required and not item.read_text().strip():
            raise ValueError('qualified package requests must be nonempty UTF-8 text')
        if hashlib.sha256(item.read_bytes()).hexdigest() != expected:
            raise ValueError('qualified package content mismatch: ' + name)
    return metadata
