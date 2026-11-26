"""File records: atomic JSON writes and SHA-256 digests."""
import hashlib
import json
from pathlib import Path


def write_json(path, value):
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    """The SHA-256 of a file's bytes."""
    return sha256(Path(path).read_bytes())
