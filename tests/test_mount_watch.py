"""Tests for polling removable media appear/disappear events."""

from pathlib import Path

from app.core.domain import MountPoint
from app.storage.mount_watch import MountChangeKind, MountWatcher
from app.storage.mounts import MountScanner


class _FakeScanner(MountScanner):
    """A MountScanner whose result can be changed between polls."""

    def __init__(self, mounts: list[MountPoint]) -> None:
        self.mounts = mounts

    def list_mounts(self) -> list[MountPoint]:
        return self.mounts


def _point(path: Path) -> MountPoint:
    return MountPoint(path=path, source="test")


def test_the_first_poll_reports_everything_present_as_appeared(tmp_path: Path) -> None:
    """There is no prior state, so whatever is there now is new."""
    scanner = _FakeScanner([_point(tmp_path / "usb")])
    watcher = MountWatcher(scanner)

    changes = watcher.poll()

    assert [(c.path, c.kind) for c in changes] == [(tmp_path / "usb", MountChangeKind.APPEARED)]


def test_an_unplugged_stick_is_reported_as_disappeared(tmp_path: Path) -> None:
    """A mount present last poll and gone this poll is a disappearance."""
    scanner = _FakeScanner([_point(tmp_path / "usb")])
    watcher = MountWatcher(scanner)
    watcher.poll()

    scanner.mounts = []
    changes = watcher.poll()

    assert [(c.path, c.kind) for c in changes] == [(tmp_path / "usb", MountChangeKind.DISAPPEARED)]


def test_an_unchanged_mount_produces_no_events(tmp_path: Path) -> None:
    """Nothing changing between polls is not reported."""
    scanner = _FakeScanner([_point(tmp_path / "usb")])
    watcher = MountWatcher(scanner)
    watcher.poll()

    changes = watcher.poll()

    assert changes == ()


def test_appearances_and_disappearances_are_both_reported_in_one_poll(tmp_path: Path) -> None:
    """A stick swapped for another between polls reports both events."""
    scanner = _FakeScanner([_point(tmp_path / "old")])
    watcher = MountWatcher(scanner)
    watcher.poll()

    scanner.mounts = [_point(tmp_path / "new")]
    changes = watcher.poll()

    assert {(c.path, c.kind) for c in changes} == {
        (tmp_path / "old", MountChangeKind.DISAPPEARED),
        (tmp_path / "new", MountChangeKind.APPEARED),
    }


def test_changes_are_sorted_by_path(tmp_path: Path) -> None:
    """Multiple simultaneous appearances come back in a stable order."""
    scanner = _FakeScanner([_point(tmp_path / "b"), _point(tmp_path / "a")])
    watcher = MountWatcher(scanner)

    changes = watcher.poll()

    assert [c.path.name for c in changes] == ["a", "b"]


def test_a_second_watcher_starts_with_no_memory_of_the_first(tmp_path: Path) -> None:
    """Watchers do not share state -- each tracks its own poll history."""
    scanner = _FakeScanner([_point(tmp_path / "usb")])
    MountWatcher(scanner).poll()

    changes = MountWatcher(scanner).poll()

    assert [(c.path, c.kind) for c in changes] == [(tmp_path / "usb", MountChangeKind.APPEARED)]
