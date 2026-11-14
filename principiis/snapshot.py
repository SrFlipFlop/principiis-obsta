"""Self-contained checkpoint trees and explicit retained-content verification."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat


def inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('snapshot root must be an existing directory, not a symlink')
    root = root.resolve()
    entries = {}
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            path = Path(directory) / name
            info = path.lstat()
            key = str(path.relative_to(root))
            if path.is_symlink():
                target = os.readlink(path)
                try:
                    resolved = path.resolve()
                except (OSError, RuntimeError) as error:
                    raise ValueError(f'unsupported snapshot symlink: {key}') from error
                if Path(target).is_absolute() or not resolved.is_relative_to(root):
                    raise ValueError(f'escaping or absolute snapshot symlink: {key}')
                entries[key] = {'link': target}
            elif stat.S_ISREG(info.st_mode):
                entries[key] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'mode': stat.S_IMODE(info.st_mode)}
            elif stat.S_ISDIR(info.st_mode):
                entries[key] = {'directory': True, 'mode': stat.S_IMODE(info.st_mode)}
            else:
                raise ValueError(f'unsupported snapshot file type: {key}')
    return entries


def preserve(workspace, snapshot):
    # Inspect links before copying; never follow a candidate link into host files.
    expected = inventory(workspace)
    shutil.copytree(workspace, snapshot, symlinks=True)
    if inventory(snapshot) != expected:
        raise ValueError('snapshot integrity changed while preserving workspace')
    snapshot.with_suffix('.json').write_text(json.dumps(expected, sort_keys=True) + '\n')


def validate(snapshot):
    snapshot = Path(snapshot)
    try:
        expected = json.loads(snapshot.with_suffix('.json').read_text())
        if inventory(snapshot) != expected:
            raise ValueError('content differs from retained manifest')
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError(f'snapshot integrity validation failed: {snapshot}: {error}') from error
