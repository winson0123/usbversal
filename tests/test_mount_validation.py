"""Tests for mount path validation at service boundaries."""

from pathlib import Path

import pytest

from app.services.bootstrap_service import bootstrap_serato_library
from app.services.crate_service import list_serato_crates
from app.services.library import open_library
from app.storage.mounts import resolve_mount_path


def test_resolve_mount_path_accepts_directory(tmp_path: Path) -> None:
    """An existing directory resolves to an absolute path."""
    assert resolve_mount_path(tmp_path) == tmp_path.resolve()


def test_resolve_mount_path_rejects_missing(tmp_path: Path) -> None:
    """A nonexistent mount fails at the boundary."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        resolve_mount_path(tmp_path / "nope")


def test_resolve_mount_path_rejects_file(tmp_path: Path) -> None:
    """A file is not a mount."""
    target = tmp_path / "file"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="not a directory"):
        resolve_mount_path(target)


@pytest.mark.parametrize(
    "service",
    [open_library, list_serato_crates, bootstrap_serato_library],
)
def test_services_reject_missing_mount(tmp_path: Path, service) -> None:
    """Every mount-taking service validates before doing vendor work."""
    with pytest.raises(FileNotFoundError):
        service(tmp_path / "nope")
