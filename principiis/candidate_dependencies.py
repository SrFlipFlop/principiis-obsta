"""Inventory retained Python environments without executing candidate files on host."""

from email.parser import BytesParser
from email.policy import default
import hashlib
from pathlib import Path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _regular(path, root):
    if path.is_symlink() or not path.is_file() or any(parent.is_symlink() for parent in path.parents if parent != root):
        raise ValueError('unsupported candidate dependency metadata: ' + str(path.relative_to(root)))


def inventory(snapshot, snapshot_manifest_sha256):
    """Record every installed distribution found in retained venv site-packages.

    The snapshot manifest separately pins all package payload bytes and modes.
    Author image inventories cover packages outside candidate virtual environments.
    """
    snapshot = Path(snapshot)
    environments = []
    for config in sorted(snapshot.rglob('pyvenv.cfg')):
        _regular(config, snapshot)
        environment = config.parent
        package_sites = sorted(path for path in environment.glob('lib*/python*/site-packages') if path.is_dir())
        sites = []
        for site in package_sites:
            if site.is_symlink():
                raise ValueError('unsupported candidate dependency metadata: ' + str(site.relative_to(snapshot)))
            packages = []
            for item in sorted(site.iterdir()):
                if item.name.endswith('.egg-info') or item.name.endswith('.egg-link'):
                    raise ValueError('unsupported candidate dependency metadata: ' + str(item.relative_to(snapshot)))
                if not item.name.endswith('.dist-info'):
                    continue
                if item.is_symlink() or not item.is_dir():
                    raise ValueError('unsupported candidate dependency metadata: ' + str(item.relative_to(snapshot)))
                metadata = item / 'METADATA'
                _regular(metadata, snapshot)
                raw = metadata.read_bytes()
                parsed = BytesParser(policy=default).parsebytes(raw, headersonly=True)
                name, version = parsed.get('Name'), parsed.get('Version')
                if not isinstance(name, str) or not name.strip() or not isinstance(version, str) or not version.strip():
                    raise ValueError('unsupported candidate dependency metadata: ' + str(metadata.relative_to(snapshot)))
                packages.append({'name': name, 'version': version,
                                 'metadata': str(metadata.relative_to(snapshot)), 'sha256': _sha(metadata)})
            sites.append({'path': str(site.relative_to(snapshot)), 'packages': packages})
        environments.append({'path': str(environment.relative_to(snapshot)),
                             'configuration_sha256': _sha(config), 'sites': sites})
    return {'schema_version': 1, 'snapshot_manifest_sha256': snapshot_manifest_sha256,
            'scope': 'retained Python virtual environments; runtime image dependencies are in the bound author inventory',
            'environments': environments}
