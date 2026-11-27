"""Find an evaluator manifest and its dependency files by SHA-256, never by trusting a path."""
import hashlib
import os
from pathlib import Path
import shutil

ENVIRONMENT = 'PRINCIPIIS_EVALUATOR_ROOT'
BENCHMARKS = Path(__file__).resolve().parents[1] / 'benchmarks'


def roots_from_environment():
    return [Path(item) for item in os.environ.get(ENVIRONMENT, '').split(os.pathsep) if item]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches(directory, name, manifest_sha256, files):
    """True only if the manifest and every recorded dependency hash match exactly."""
    try:
        manifest = directory / name
        if not manifest.is_file() or _sha(manifest) != manifest_sha256:
            return False
        for relative, expected in files.items():
            if Path(relative).is_absolute() or '..' in Path(relative).parts:
                return False
            path = directory / relative
            # The same rule the evaluator applies at use (`assessment._relative`).
            if path.resolve() != path or not path.is_file() or _sha(path) != expected:
                return False
        return True
    except OSError:
        return False


def _candidates(recorded, extra_roots):
    yield recorded.parent
    if BENCHMARKS.is_dir():
        yield from sorted(BENCHMARKS.glob('*/evaluator/*/'))
    for root in extra_roots:
        root = Path(root)
        if root.is_dir():
            yield root
            yield from sorted(path.parent for path in root.rglob(recorded.name))


def locate(recorded_manifest, manifest_sha256, files, *, extra_roots=()):
    """Return the manifest path whose own and dependency hashes all match the record.

    Order: the recorded path, the repository's benchmarks/*/evaluator/*/ tree, then any
    configured roots. Same-named files with different content are skipped; the first
    complete hash match wins (all matches are byte-identical by construction).
    """
    recorded = Path(recorded_manifest)
    for directory in _candidates(recorded, extra_roots):
        # Content is what is trusted, so a symlinked location is followed, then checked as resolved.
        try:
            directory = directory.resolve()
        except OSError:
            continue
        if _matches(directory, recorded.name, manifest_sha256, files):
            return directory / recorded.name
    raise ValueError('retained evaluator not found by SHA-256 (searched the recorded path, '
                     'benchmarks/*/evaluator/*/ and --evaluator-root / ' + ENVIRONMENT
                     + '); retained evaluator binding changed or unavailable')


# Location fields are audit-only: identity is the hashes in the rest of the record, never a path.
LOCATION_FIELDS = ('manifest', 'source_manifest')


def identity(binding):
    return {key: value for key, value in binding.items() if key not in LOCATION_FIELDS}


def copy_evaluator(root, declaration, manifest_sha256, files):
    """Make a run self-contained: copy the manifest and its hashed dependency files into it.

    Returns the run-relative manifest path. Every copied byte is checked against the
    recorded hashes, and the copy is staged and renamed so a failed bind never leaves
    a half-written `evaluator/` directory.
    """
    declaration = Path(declaration).resolve()
    target, staging = Path(root) / 'evaluator', Path(root) / 'evaluator.partial'
    for stale in (target, staging):
        if stale.is_symlink() or stale.is_file():
            raise ValueError('evaluator copy location is not a directory')
        if stale.exists():
            shutil.rmtree(stale)
    expected = dict(files, **{declaration.name: manifest_sha256})
    try:
        for name, sha256 in expected.items():
            content = (declaration.parent / name).read_bytes()
            if hashlib.sha256(content).hexdigest() != sha256:
                raise ValueError('evaluator dependency content changed: ' + str(name))
            destination = staging / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    staging.rename(target)
    return 'evaluator/' + declaration.name


def evaluator_directory(root, binding, search_roots=()):
    """The directory holding the bound evaluator: the run's own copy, else found by SHA-256."""
    recorded = binding['manifest']
    if not Path(recorded).is_absolute():
        path = Path(root) / recorded
        if '..' in Path(recorded).parts or path.is_symlink() or path.resolve() != path or not path.is_file():
            raise ValueError('retained evaluator copy must be a regular file inside the run')
        if _sha(path) != binding['manifest_sha256']:
            raise ValueError('retained evaluator manifest content changed')
        return path.parent
    return locate(recorded, binding['manifest_sha256'], binding['files'],
                  extra_roots=[*search_roots, *roots_from_environment()]).parent
