"""Keep the two shipped version strings the same."""

import tomllib
from pathlib import Path

import app


def _pyproject_version() -> str:
    """
    Return ``project.version`` from the repo ``pyproject.toml``.

    Returns:
        The version string declared for the package.
    """
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_app_version_matches_pyproject() -> None:
    """``app.__version__`` must match ``pyproject.toml``."""
    assert app.__version__ == _pyproject_version()
