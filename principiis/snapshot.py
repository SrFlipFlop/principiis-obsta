"""Checkpoint trees with self-contained or explicitly image-bound symlinks."""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat


_UNSPECIFIED = object()


def _binding(binding):
    if binding is None:
        return None, set()
    if (not isinstance(binding, dict) or set(binding) != {'image', 'symlink_targets'}
            or not isinstance(binding['image'], str)
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', binding['image'])
            or not isinstance(binding['symlink_targets'], list)
            or not all(isinstance(target, str) and target.startswith('/')
                       and str(Path(target)) == target and '..' not in Path(target).parts
                       and not any(c in target for c in ('\x00', '\n', '\r'))
                       for target in binding['symlink_targets'])):
        raise ValueError('invalid snapshot runtime binding')
    return binding['image'], set(binding['symlink_targets'])


def _verify_link(key, entries, runtime_targets):
    """Resolve only retained lexical links; never ask the host to resolve targets."""
    pending = deque(Path(key).parts)
    components = []
    expansions = 0
    while pending:
        part = pending.popleft()
        if part == '.':
            continue
        if part == '..':
            if not components:
                raise ValueError(f'escaping snapshot symlink: {key}')
            components.pop()
            continue
        components.append(part)
        item = entries.get('/'.join(components), {})
        if 'link' not in item:
            if pending and 'sha256' in item:
                raise ValueError(f'non-directory traversal in snapshot symlink: {key}')
            continue
        expansions += 1
        if expansions > 40:
            raise ValueError(f'cyclic or excessive snapshot symlink chain: {key}')
        target = item['link']
        if Path(target).is_absolute():
            if target not in runtime_targets or pending:
                raise ValueError(f'escaping or absolute snapshot symlink: {key}')
            return
        components.pop()
        pending.extendleft(reversed(Path(target).parts))


def inventory(root, *, runtime_binding=None):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('snapshot root must be an existing directory, not a symlink')
    # abspath is lexical. Path.resolve() could follow a candidate link on the host.
    root = Path(os.path.abspath(root))
    image, runtime_targets = _binding(runtime_binding)
    entries = {}
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            path = Path(directory) / name
            info = path.lstat()
            key = str(path.relative_to(root))
            if path.is_symlink():
                target = os.readlink(path)
                entries[key] = {'link': target}
                if Path(target).is_absolute() and target in runtime_targets:
                    entries[key]['runtime_image'] = image
            elif stat.S_ISREG(info.st_mode):
                entries[key] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'mode': stat.S_IMODE(info.st_mode)}
            elif stat.S_ISDIR(info.st_mode):
                entries[key] = {'directory': True, 'mode': stat.S_IMODE(info.st_mode)}
            else:
                raise ValueError(f'unsupported snapshot file type: {key}')
    for key, item in entries.items():
        if 'link' in item:
            _verify_link(key, entries, runtime_targets)
    return entries


def preserve(workspace, snapshot, *, runtime_binding=None):
    # Inspect links before copying; never follow a candidate link into host files.
    expected = inventory(workspace, runtime_binding=runtime_binding)
    shutil.copytree(workspace, snapshot, symlinks=True)
    if inventory(snapshot, runtime_binding=runtime_binding) != expected:
        raise ValueError('snapshot integrity changed while preserving workspace')
    snapshot.with_suffix('.json').write_text(json.dumps(expected, sort_keys=True) + '\n')


def validate(snapshot, *, runtime_image=_UNSPECIFIED):
    """Verify retained bytes. Consumers must pass their image (None for host tools).

    Omitting runtime_image permits read-only integrity/status checks. It does not
    authorize consuming image-bound links on the controller host.
    """
    snapshot = Path(snapshot)
    try:
        expected = json.loads(snapshot.with_suffix('.json').read_text())
        if not isinstance(expected, dict) or not all(isinstance(item, dict) for item in expected.values()):
            raise ValueError('invalid retained manifest')
        if any(not isinstance(item.get('runtime_image'), str) for item in expected.values() if 'runtime_image' in item):
            raise ValueError('invalid retained runtime image binding')
        images = {item['runtime_image'] for item in expected.values() if 'runtime_image' in item}
        if len(images) > 1:
            raise ValueError('snapshot has inconsistent runtime image bindings')
        binding = None
        if images:
            image = next(iter(images))
            binding = {'image': image, 'symlink_targets': [item.get('link') for item in expected.values() if 'runtime_image' in item]}
            _binding(binding)
            if runtime_image is not _UNSPECIFIED and runtime_image != image:
                raise ValueError('snapshot requires its attested runtime image; host or different-image consumption is unsupported')
        if inventory(snapshot, runtime_binding=binding) != expected:
            raise ValueError('content differs from retained manifest')
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError(f'snapshot integrity validation failed: {snapshot}: {error}') from error


def forbid_foreign_git(root):
    """Reject Git metadata that points outside the workspace (issue #75 item 1).

    A development workspace starts empty and only receives the agent's own prior
    checkpoint. A self-contained repository the agent created is its own work and is
    allowed. A gitfile, symlinked `.git`, `commondir` or object alternates would let
    the agent read research-side history by path, so they fail before the stage.
    """
    root = Path(os.path.abspath(root))
    problems = []
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            if name != '.git':
                continue
            path = Path(directory) / name
            where = str(path.relative_to(root))
            if path.is_symlink():
                problems.append(f'{where} is a symlink')
            elif path.is_file():
                problems.append(f'{where} is a gitfile pointing elsewhere')
            else:
                for extra in ('commondir', 'objects/info/alternates'):
                    if (path / extra).exists() or (path / extra).is_symlink():
                        problems.append(f'{where}/{extra} references another repository')
    if problems:
        raise ValueError('workspace contains research-side Git references: ' + '; '.join(problems))
