"""Resolve evaluator file arguments against the trusted task package."""
from pathlib import Path


def check_argv(directory, argv):
    directory = Path(directory)
    return [str((directory / arg).resolve()) if (directory / arg).is_file() else arg for arg in argv]
