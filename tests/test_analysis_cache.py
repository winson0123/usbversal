"""Tests for host volume dirs and the analysis-ported disk cache."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.adapters.rekordbox.anlz import extended_path
from app.services.cancellation import OperationCancelled, clear_quit_request
from app.services.sync_analysis import AnalysisTrackResult
from app.services.track_sync import (
    apply_analysis_cache_from_results,
    warm_analysis_ported_cache,
)
from app.storage.analysis_cache import (
    CACHE_VERSION,
    analysis_cache_path,
    fingerprint,
    load_analysis_cache,
    relative_to_mount,
    save_analysis_cache,
)
from app.storage.host import host_volume_dir
from tests.test_sync_state import _DAT_REL, _write_audio, _write_dat


def test_host_volume_dir_uses_mount_label(tmp_path: Path, monkeypatch: pytest.Monkeypatch) -> None:
    """Host data is namespaced by volume label, not an arbitrary folder spelling."""
    monkeypatch.setenv("USBVERSAL_DATA_ROOT", str(tmp_path / "host"))
    mount = tmp_path / "WONSIN21"
    mount.mkdir()
    with patch("app.storage.host.mount_label_name", return_value="WONSIN2"):
        root = host_volume_dir(mount)
    assert root.name == "WONSIN2"
    assert root.parent == (tmp_path / "host").resolve()


def test_corrupt_cache_loads_empty(tmp_path: Path, monkeypatch: pytest.Monkeypatch) -> None:
    """A broken JSON file is ignored rather than crashing the check."""
    monkeypatch.setenv("USBVERSAL_DATA_ROOT", str(tmp_path / "host"))
    mount = tmp_path / "stick"
    mount.mkdir()
    path = analysis_cache_path(mount)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_analysis_cache(mount) == {}


def test_warm_persists_and_second_pass_skips_probe(
    tmp_path: Path, monkeypatch: pytest.Monkeypatch
) -> None:
    """A completed warm writes the cache; a second warm reuses hits."""
    monkeypatch.setenv("USBVERSAL_DATA_ROOT", str(tmp_path / "host"))
    mount = tmp_path / "stick"
    mount.mkdir()
    _write_dat(mount, _DAT_REL, [(1, 128.0, 0)])
    _write_audio(mount, "Contents/a.mp3", beatgrid=True)
    content = SimpleNamespace(analysis_data_file_path=f"/{_DAT_REL}")
    tracks = [("/Contents/a.mp3", content)]

    warm_analysis_ported_cache(mount, tracks, {})
    assert analysis_cache_path(mount).is_file()
    disk = load_analysis_cache(mount)
    assert disk
    assert all(entry["ported"] is True for entry in disk.values())

    calls: list[object] = []

    def boom(*_args: object, **_kwargs: object) -> bool:
        """Fail if a live probe runs on a cache hit."""
        calls.append(1)
        raise AssertionError("probe should not run on a fingerprint hit")

    cache: dict[str, bool] = {}
    with patch("app.services.track_sync._analysis_is_ported", side_effect=boom):
        warm_analysis_ported_cache(mount, tracks, cache)
    assert calls == []
    assert any(cache.values())


def test_stale_audio_fingerprint_reprobes(tmp_path: Path, monkeypatch: pytest.Monkeypatch) -> None:
    """Changing the audio file size invalidates the cached verdict."""
    monkeypatch.setenv("USBVERSAL_DATA_ROOT", str(tmp_path / "host"))
    mount = tmp_path / "stick"
    mount.mkdir()
    _write_dat(mount, _DAT_REL, [(1, 128.0, 0)])
    _write_audio(mount, "Contents/a.mp3", beatgrid=False)
    content = SimpleNamespace(analysis_data_file_path=f"/{_DAT_REL}")
    tracks = [("/Contents/a.mp3", content)]

    warm_analysis_ported_cache(mount, tracks, {})
    audio = mount / "Contents/a.mp3"
    audio.write_bytes(audio.read_bytes() + b"\x00")

    probes = {"n": 0}
    from app.services import track_sync as track_sync_mod

    real = track_sync_mod._analysis_is_ported

    def counting(dat_path: Path | None, audio_path: Path) -> bool:
        """Count live probes while delegating to the real checker."""
        probes["n"] += 1
        return real(dat_path, audio_path)

    cache: dict[str, bool] = {}
    with patch("app.services.track_sync._analysis_is_ported", side_effect=counting):
        warm_analysis_ported_cache(mount, tracks, cache)
    assert probes["n"] == 1
    assert list(cache.values()) == [False]


def test_cancel_mid_warm_does_not_write_cache(
    tmp_path: Path, monkeypatch: pytest.Monkeypatch
) -> None:
    """A cancelled warm must not create or update analysis-cache.json."""
    clear_quit_request()
    monkeypatch.setenv("USBVERSAL_DATA_ROOT", str(tmp_path / "host"))
    monkeypatch.setenv("USBVERSAL_SYNC_WORKERS", "1")
    mount = tmp_path / "stick"
    mount.mkdir()
    tracks = []
    for index in range(5):
        rel = f"Contents/t{index}.mp3"
        _write_dat(mount, f"USBANLZ/t{index}.DAT", [(1, 120.0, 0)])
        _write_audio(mount, rel, beatgrid=False)
        tracks.append(
            (
                f"/{rel}",
                SimpleNamespace(analysis_data_file_path=f"/USBANLZ/t{index}.DAT"),
            )
        )
    seen = {"n": 0}

    def cancel_after_first() -> bool:
        """Flip true after the first probe starts counting."""
        seen["n"] += 1
        return seen["n"] > 1

    with pytest.raises(OperationCancelled):
        warm_analysis_ported_cache(mount, tracks, {}, should_cancel=cancel_after_first)
    assert not analysis_cache_path(mount).exists()


def test_apply_sync_results_updates_and_removes_entries(
    tmp_path: Path, monkeypatch: pytest.Monkeypatch
) -> None:
    """Successful analysis marks ported; errors drop the cache entry."""
    monkeypatch.setenv("USBVERSAL_DATA_ROOT", str(tmp_path / "host"))
    mount = tmp_path / "stick"
    mount.mkdir()
    _write_dat(mount, _DAT_REL, [(1, 128.0, 0)])
    _write_audio(mount, "Contents/a.mp3", beatgrid=True)
    content_a = SimpleNamespace(path="/Contents/a.mp3", analysis_data_file_path=f"/{_DAT_REL}")
    contents = {
        "/Contents/a.mp3": content_a,
        "Contents/a.mp3": content_a,
    }
    bad_key = f"{_DAT_REL}|Contents/a.mp3"
    save_analysis_cache(
        mount,
        {
            bad_key: {
                "ported": False,
                "audio": list(fingerprint(mount / "Contents/a.mp3")),
                "dat": list(fingerprint(mount / _DAT_REL)),
                "ext": list(fingerprint(extended_path(mount / _DAT_REL))),
            },
            "|Contents/missing.mp3": {
                "ported": True,
                "audio": [0, 0],
                "dat": [0, 0],
                "ext": [0, 0],
            },
        },
    )
    apply_analysis_cache_from_results(
        mount,
        [
            AnalysisTrackResult("/Contents/a.mp3", None, None, False, True),
            AnalysisTrackResult(
                "/Contents/missing.mp3", "audio file is missing", None, False, False
            ),
        ],
        contents,
    )
    disk = load_analysis_cache(mount)
    assert disk[bad_key]["ported"] is True
    assert "|Contents/missing.mp3" not in disk


def test_save_round_trip_version(tmp_path: Path, monkeypatch: pytest.Monkeypatch) -> None:
    """Saved cache carries version 1 and reloads tracks."""
    monkeypatch.setenv("USBVERSAL_DATA_ROOT", str(tmp_path / "host"))
    mount = tmp_path / "stick"
    mount.mkdir()
    (mount / "Contents").mkdir()
    audio = mount / "Contents" / "a.mp3"
    audio.write_bytes(b"x")
    key = f"|{relative_to_mount(mount, audio)}"
    save_analysis_cache(
        mount,
        {
            key: {
                "ported": True,
                "audio": list(fingerprint(audio)),
                "dat": [0, 0],
                "ext": [0, 0],
            }
        },
    )
    raw = json.loads(analysis_cache_path(mount).read_text(encoding="utf-8"))
    assert raw["version"] == CACHE_VERSION
    assert load_analysis_cache(mount)[key]["ported"] is True
