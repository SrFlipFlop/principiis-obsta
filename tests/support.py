"""Shared test helpers."""
from pathlib import Path
import tempfile


def temporary_directory(**kwargs):
    """A TemporaryDirectory whose name is fully resolved.

    The default macOS TMPDIR lives under the /var -> /private/var symlink,
    and production code rejects or resolves symlinked paths.
    """
    kwargs.setdefault('dir', Path(tempfile.gettempdir()).resolve())
    return tempfile.TemporaryDirectory(**kwargs)
