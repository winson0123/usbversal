"""Tests for syncing playlists into Serato crates."""

import shutil
import sqlite3
import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.adapters.serato import read_crate_track_paths, read_database_track_paths
from app.adapters.serato.library_db import library_db_path, read_track_analysis
from app.adapters.serato.neworder import read_crate_order, write_crate_order
from app.adapters.serato.tags import read_geob
from app.core.domain import Playlist
from app.services.migration_service import PlaylistNotFoundError, SeratoLibraryRequiredError
from app.services.sync_service import SyncProgress, correct_index_bpm, sync_playlists
from app.storage.backup import BackupManifest, default_backup_root
from tests.conftest import EMPTY_DATABASE_V2, make_library

TRACKS = ["/Contents/a.mp3", "/Contents/b.mp3"]
FIXTURES = Path(__file__).parent / "fixtures" / "serato"

_ASSET_SCHEMA = """
create table asset (
    id integer primary key autoincrement,
    revision integer not null,
    portable_id text,
    file_name text,
    key text not null default '',
    bpm real,
    is_stale integer not null default 0
);
create table space (id integer, name text, revision integer);
create table serato (database_name text, revision integer);
create table master (uuid blob, revision integer);
"""


def _section(tag: bytes, header_extra: bytes, body: bytes) -> bytes:
    """Build one ANLZ section with its header and total lengths."""
    header_len = 12 + len(header_extra)
    total_len = header_len + len(body)
    return tag + struct.pack(">II", header_len, total_len) + header_extra + body


def _anlz(sections: bytes) -> bytes:
    """Wrap sections in a PMAI container."""
    return b"PMAI" + struct.pack(">II", 28, 28 + len(sections)) + b"\x00" * 16 + sections


def _pqtz(beats: list[tuple[int, float, int]]) -> bytes:
    """Build a PQTZ beat grid section."""
    body = b"".join(struct.pack(">HHI", n, int(bpm * 100), t) for n, bpm, t in beats)
    return _section(b"PQTZ", b"\x00" * 12, body)


def _cue(number: int, time_ms: int, colour: tuple[int, int, int]) -> bytes:
    """Build one PCO2 extended cue entry."""
    body = b"\x01\x00\x03\xe8" + struct.pack(">I", time_ms) + b"\x00" * 20 + b"\x00"
    body += bytes(colour)
    return b"PCP2" + struct.pack(">II", 16, 16 + len(body)) + struct.pack(">I", number) + body


def _pco2(kind: int, cues: list[bytes]) -> bytes:
    """Build a PCO2 cue-list section; kind 1 is hot cues."""
    extra = struct.pack(">IHH", kind, len(cues), 0)
    return _section(b"PCO2", extra, b"".join(cues))


def _write_analysis(
    dat_path: Path, *, beats: list[tuple[int, float, int]], cues: list[tuple[int, int, tuple]]
) -> None:
    """Write a .DAT/.EXT pair holding a beatgrid and extended cues."""
    dat_path.parent.mkdir(parents=True, exist_ok=True)
    dat_path.write_bytes(_anlz(_pqtz(beats)))
    ext = dat_path.with_suffix(".EXT")
    ext.write_bytes(_anlz(_pco2(1, [_cue(n, t, c) for n, t, c in cues])))


def _stick(
    root: Path,
    *,
    indexed: list[str],
    order: list[str] | None = None,
    asset_rows: dict[str, tuple[float, str]] | None = None,
) -> Path:
    """Create a mount with a Rekordbox export and a Serato library."""
    rb = root / "PIONEER" / "rekordbox"
    rb.mkdir(parents=True)
    (rb / "exportLibrary.db").write_bytes(b"stub")

    serato = root / "_Serato_"
    (serato / "Subcrates").mkdir(parents=True)
    blob = EMPTY_DATABASE_V2
    for path in indexed:
        inner = (
            b"pfil" + struct.pack(">I", len(path.encode("utf-16-be"))) + path.encode("utf-16-be")
        )
        blob += b"otrk" + struct.pack(">I", len(inner)) + inner
    (serato / "database V2").write_bytes(blob)
    if order is not None:
        write_crate_order(serato, order)

    if asset_rows is not None:
        index_path = library_db_path(serato)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(index_path)
        con.executescript(_ASSET_SCHEMA)
        con.executemany(
            "insert into asset (revision, portable_id, file_name, key, bpm) values (?,?,?,?,?)",
            [(10, path, Path(path).name, key, bpm) for path, (bpm, key) in asset_rows.items()],
        )
        con.execute("insert into space values (1, 'Serato Library', 10)")
        con.execute("insert into serato values ('', 10)")
        con.execute("insert into master values (x'00', 10)")
        con.commit()
        con.close()
    return root


def _library(
    mount: Path, playlists: list[Playlist], tracks: dict[int, list[str]], contents=None, keys=None
):
    """Build a session handle over a stubbed Rekordbox adapter."""
    adapter = MagicMock()
    adapter.list_playlists.return_value = playlists
    adapter.get_playlist_track_paths.side_effect = lambda pid: tracks[pid]
    database = MagicMock()
    database.get_artists.return_value = []
    database.get_albums.return_value = []
    database.get_genres.return_value = []
    database.get_keys.return_value = keys or []
    database.get_contents.return_value = contents or []
    adapter.database = database
    return make_library(mount, adapter)


def _content(
    path: str, *, analysis_data_file_path: str | None = None, key_id: int | None = None
) -> SimpleNamespace:
    """Minimal Rekordbox content row."""
    return SimpleNamespace(
        path=path,
        title="T",
        artist_id=None,
        album_id=None,
        genre_id=None,
        key_id=key_id,
        length=10,
        file_size=1000,
        bitrate=320,
        sampling_rate=44100,
        bpmx100=12800,
        release_year=0,
        release_date="",
        date_added=None,
        analysis_data_file_path=analysis_data_file_path,
    )


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    """A dry run reports the plan and leaves the stick untouched."""
    mount = _stick(tmp_path, indexed=[])
    before = (mount / "_Serato_" / "database V2").read_bytes()
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: TRACKS})

    report = sync_playlists(library, [1], dry_run=True)

    assert report.dry_run is True
    assert report.backup_id is None
    assert report.records_added == 2
    assert (mount / "_Serato_" / "database V2").read_bytes() == before
    assert not list((mount / "_Serato_" / "Subcrates").glob("*.crate"))


def test_sync_indexes_missing_tracks_and_writes_a_crate(tmp_path: Path) -> None:
    """Tracks Serato does not know are added, then placed in a crate."""
    mount = _stick(tmp_path, indexed=[])
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: TRACKS}, [_content(t) for t in TRACKS])

    calls: list[SyncProgress] = []
    report = sync_playlists(library, [1], on_progress=calls.append)

    assert [sample.phase for sample in calls if sample.phase == "index"] == ["index", "index"]
    assert report.records_added == 2
    assert report.crates_written == 1
    assert report.backup_id is not None
    crate = mount / "_Serato_" / "Subcrates" / "test.crate"
    assert read_crate_track_paths(crate) == ["Contents/a.mp3", "Contents/b.mp3"]
    assert read_database_track_paths(mount / "_Serato_" / "database V2") == [
        "Contents/a.mp3",
        "Contents/b.mp3",
    ]


def test_already_indexed_tracks_are_not_duplicated(tmp_path: Path) -> None:
    """Tracks Serato already knows are not added a second time."""
    mount = _stick(tmp_path, indexed=["Contents/a.mp3"])
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: TRACKS}, [_content(t) for t in TRACKS])

    report = sync_playlists(library, [1])

    assert report.records_added == 1
    assert (
        read_database_track_paths(mount / "_Serato_" / "database V2").count("Contents/a.mp3") == 1
    )


def test_shared_tracks_are_indexed_once_across_playlists(tmp_path: Path) -> None:
    """A track in two selected playlists produces one database record."""
    mount = _stick(tmp_path, indexed=[])
    playlists = [
        Playlist(id=1, name="one", parent_id=None, is_folder=False),
        Playlist(id=2, name="two", parent_id=None, is_folder=False),
    ]
    library = _library(mount, playlists, {1: TRACKS, 2: TRACKS}, [_content(t) for t in TRACKS])

    report = sync_playlists(library, [1, 2])

    assert report.records_added == 2
    assert report.crates_written == 2


def test_existing_crate_order_is_preserved(tmp_path: Path) -> None:
    """New crates append to the display order rather than replacing it."""
    mount = _stick(tmp_path, indexed=[], order=["Pocket"])
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: TRACKS}, [_content(t) for t in TRACKS])

    sync_playlists(library, [1])

    assert read_crate_order(mount / "_Serato_") == ["Pocket", "test"]


def test_unknown_playlist_is_rejected(tmp_path: Path) -> None:
    """Selecting a missing playlist fails before anything is written."""
    mount = _stick(tmp_path, indexed=[])
    library = _library(mount, [], {})

    with pytest.raises(PlaylistNotFoundError):
        sync_playlists(library, [99])


def test_folder_cannot_be_synced(tmp_path: Path) -> None:
    """Folders hold no tracks and are not valid selections."""
    mount = _stick(tmp_path, indexed=[])
    folder = Playlist(id=9, name="Genres", parent_id=None, is_folder=True)
    library = _library(mount, [folder], {})

    with pytest.raises(PlaylistNotFoundError):
        sync_playlists(library, [9])


def test_each_crate_holds_only_its_own_tracks(tmp_path: Path) -> None:
    """Writing several crates in one run must not leak tracks between them.

    serato-tools keeps DEFAULT_ENTRIES at class level and add_track mutates it,
    so a new crate would otherwise inherit every track added before it.
    """
    mount = _stick(tmp_path, indexed=[])
    playlists = [
        Playlist(id=1, name="one", parent_id=None, is_folder=False),
        Playlist(id=2, name="two", parent_id=None, is_folder=False),
    ]
    tracks = {1: ["/Contents/one.mp3"], 2: ["/Contents/two.mp3"]}
    contents = [_content("/Contents/one.mp3"), _content("/Contents/two.mp3")]
    library = _library(mount, playlists, tracks, contents)

    sync_playlists(library, [1, 2])

    subcrates = mount / "_Serato_" / "Subcrates"
    assert read_crate_track_paths(subcrates / "one.crate") == ["Contents/one.mp3"]
    assert read_crate_track_paths(subcrates / "two.crate") == ["Contents/two.mp3"]


def _place_audio(mount: Path, relative: str) -> Path:
    """Copy the fixture WAV to a track path under the mount."""
    target = mount / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "Techno1.BEFORE.wav", target)
    return target


def test_analysis_writes_beatgrid_cues_and_index(tmp_path: Path) -> None:
    """A track with Rekordbox analysis gets a grid, cues, and an updated index row."""
    mount = _stick(
        tmp_path,
        indexed=["Contents/track.wav"],
        asset_rows={"Contents/track.wav": (999.0, "")},
    )
    _place_audio(mount, "Contents/track.wav")
    dat = mount / "PIONEER" / "USBANLZ" / "P001" / "ANLZ0000.DAT"
    _write_analysis(
        dat,
        beats=[(1, 136.0, 0), (2, 136.0, 441), (3, 136.0, 882)],
        cues=[(1, 0, (0xFF, 0x00, 0x17)), (2, 441, (0x00, 0xC4, 0xFF))],
    )
    content = _content(
        "/Contents/track.wav",
        analysis_data_file_path="/PIONEER/USBANLZ/P001/ANLZ0000.DAT",
        key_id=5,
    )
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(
        mount,
        [playlist],
        {1: ["/Contents/track.wav"]},
        [content],
        keys=[SimpleNamespace(id=5, name="8A")],
    )

    report = sync_playlists(library, [1])

    assert report.grids_written == 1
    assert report.cues_written == 1
    assert report.index_rows_updated == 1
    assert report.analysis_errors == ()

    frames = read_geob(mount / "Contents" / "track.wav")
    assert frames["Serato BeatGrid"]
    assert frames["Serato Markers2"]

    analysis = read_track_analysis(library_db_path(mount / "_Serato_"))["Contents/track.wav"]
    assert analysis.bpm == 136.0
    assert analysis.key == "8A"


def test_no_analysis_data_leaves_index_untouched(tmp_path: Path) -> None:
    """A track Rekordbox never analysed is left exactly as Serato had it."""
    mount = _stick(
        tmp_path, indexed=["Contents/track.wav"], asset_rows={"Contents/track.wav": (99.0, "Am")}
    )
    _place_audio(mount, "Contents/track.wav")
    content = _content("/Contents/track.wav")
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: ["/Contents/track.wav"]}, [content])

    report = sync_playlists(library, [1])

    assert report.grids_written == 0
    assert report.index_rows_updated == 0
    analysis = read_track_analysis(library_db_path(mount / "_Serato_"))["Contents/track.wav"]
    assert (analysis.bpm, analysis.key) == (99.0, "Am")


def test_malformed_analysis_is_skipped_not_fatal(tmp_path: Path) -> None:
    """A corrupt ANLZ file is recorded as an error but does not abort the sync."""
    mount = _stick(tmp_path, indexed=["Contents/track.wav"])
    _place_audio(mount, "Contents/track.wav")
    dat = mount / "PIONEER" / "USBANLZ" / "P001" / "ANLZ0000.DAT"
    dat.parent.mkdir(parents=True)
    dat.write_bytes(b"NOPE" + b"\x00" * 40)
    content = _content(
        "/Contents/track.wav", analysis_data_file_path="/PIONEER/USBANLZ/P001/ANLZ0000.DAT"
    )
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: ["/Contents/track.wav"]}, [content])

    report = sync_playlists(library, [1])

    assert report.grids_written == 0
    assert len(report.analysis_errors) == 1
    assert report.crates_written == 1


def test_analysis_targets_are_backed_up(tmp_path: Path) -> None:
    """The audio file about to be tagged is captured in the run's backup."""
    mount = _stick(tmp_path, indexed=["Contents/track.wav"])
    _place_audio(mount, "Contents/track.wav")
    dat = mount / "PIONEER" / "USBANLZ" / "P001" / "ANLZ0000.DAT"
    _write_analysis(dat, beats=[(1, 128.0, 0)], cues=[])
    content = _content(
        "/Contents/track.wav", analysis_data_file_path="/PIONEER/USBANLZ/P001/ANLZ0000.DAT"
    )
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: ["/Contents/track.wav"]}, [content])

    report = sync_playlists(library, [1])

    backup_dir = default_backup_root(mount) / report.backup_id
    manifest = BackupManifest.load(backup_dir)
    entry = next(e for e in manifest.files if e.relative_path == "Contents/track.wav")
    assert (backup_dir / entry.artifact_path()).is_file()
    assert not (mount / "backups").exists()


def test_correct_index_bpm_fixes_a_wrong_row(tmp_path: Path) -> None:
    """A row that disagrees with the first beat's tempo is corrected."""
    mount = _stick(
        tmp_path,
        indexed=["Contents/track.wav"],
        asset_rows={"Contents/track.wav": (106.0, "")},
    )
    dat = mount / "PIONEER" / "USBANLZ" / "P001" / "ANLZ0000.DAT"
    _write_analysis(dat, beats=[(1, 126.0, 0), (2, 126.0, 476)], cues=[])
    content = _content(
        "/Contents/track.wav", analysis_data_file_path="/PIONEER/USBANLZ/P001/ANLZ0000.DAT"
    )
    library = _library(mount, [], {}, [content])

    result = correct_index_bpm(library)

    assert result.candidates == 1
    assert result.rows_updated == 1
    assert result.backup_id is not None
    analysis = read_track_analysis(library_db_path(mount / "_Serato_"))["Contents/track.wav"]
    assert analysis.bpm == 126.0


def test_correct_index_bpm_leaves_matching_rows_alone(tmp_path: Path) -> None:
    """A row that already agrees with the grid is not rewritten."""
    mount = _stick(
        tmp_path,
        indexed=["Contents/track.wav"],
        asset_rows={"Contents/track.wav": (128.0, "")},
    )
    dat = mount / "PIONEER" / "USBANLZ" / "P001" / "ANLZ0000.DAT"
    _write_analysis(dat, beats=[(1, 128.0, 0)], cues=[])
    content = _content(
        "/Contents/track.wav", analysis_data_file_path="/PIONEER/USBANLZ/P001/ANLZ0000.DAT"
    )
    library = _library(mount, [], {}, [content])

    result = correct_index_bpm(library)

    assert result.candidates == 1
    assert result.rows_updated == 0
    assert result.backup_id is None


def test_correct_index_bpm_dry_run_writes_nothing(tmp_path: Path) -> None:
    """A dry run previews the count and leaves the index untouched."""
    mount = _stick(
        tmp_path,
        indexed=["Contents/track.wav"],
        asset_rows={"Contents/track.wav": (106.0, "")},
    )
    index_path = library_db_path(mount / "_Serato_")
    before = index_path.read_bytes()
    dat = mount / "PIONEER" / "USBANLZ" / "P001" / "ANLZ0000.DAT"
    _write_analysis(dat, beats=[(1, 126.0, 0)], cues=[])
    content = _content(
        "/Contents/track.wav", analysis_data_file_path="/PIONEER/USBANLZ/P001/ANLZ0000.DAT"
    )
    library = _library(mount, [], {}, [content])

    result = correct_index_bpm(library, dry_run=True)

    assert result.rows_updated == 1
    assert result.backup_id is None
    assert index_path.read_bytes() == before


def test_correct_index_bpm_skips_tracks_serato_does_not_know(tmp_path: Path) -> None:
    """A track with no existing index row is never inserted."""
    mount = _stick(tmp_path, indexed=[], asset_rows={})
    dat = mount / "PIONEER" / "USBANLZ" / "P001" / "ANLZ0000.DAT"
    _write_analysis(dat, beats=[(1, 126.0, 0)], cues=[])
    content = _content(
        "/Contents/track.wav", analysis_data_file_path="/PIONEER/USBANLZ/P001/ANLZ0000.DAT"
    )
    library = _library(mount, [], {}, [content])

    result = correct_index_bpm(library)

    assert result.candidates == 0
    assert result.rows_updated == 0


def test_correct_index_bpm_requires_an_index_file(tmp_path: Path) -> None:
    """A Serato library with no location.sqlite yet cannot be corrected."""
    mount = _stick(tmp_path, indexed=[])
    library = _library(mount, [], {}, [])

    with pytest.raises(SeratoLibraryRequiredError):
        correct_index_bpm(library)


def test_on_progress_reports_each_analysis_track(tmp_path: Path) -> None:
    """A progress callback fires once per track with real analysis data."""
    mount = _stick(tmp_path, indexed=["Contents/a.wav", "Contents/b.wav"])
    for name in ("a", "b"):
        _place_audio(mount, f"Contents/{name}.wav")
        dat = mount / "PIONEER" / "USBANLZ" / name / "ANLZ0000.DAT"
        _write_analysis(dat, beats=[(1, 128.0, 0)], cues=[])
    contents = [
        _content(
            f"/Contents/{name}.wav", analysis_data_file_path=f"/PIONEER/USBANLZ/{name}/ANLZ0000.DAT"
        )
        for name in ("a", "b")
    ]
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: ["/Contents/a.wav", "/Contents/b.wav"]}, contents)
    calls: list[SyncProgress] = []

    sync_playlists(library, [1], on_progress=calls.append)

    analysis = [sample for sample in calls if sample.phase == "analysis"]
    crates = [sample for sample in calls if sample.phase == "crates"]
    assert analysis == [
        SyncProgress("analysis", 1, 2, "/Contents/a.wav"),
        SyncProgress("analysis", 2, 2, "/Contents/b.wav"),
    ]
    assert crates == [SyncProgress("crates", 1, 1, "test")]


def test_on_progress_reports_the_failing_track_and_its_error(tmp_path: Path) -> None:
    """A track whose analysis fails is reported with its own error message,
    not just folded silently into the done/total counts."""
    mount = _stick(tmp_path, indexed=["Contents/a.wav"])
    _place_audio(mount, "Contents/a.wav")
    dat = mount / "PIONEER" / "USBANLZ" / "a" / "ANLZ0000.DAT"
    dat.parent.mkdir(parents=True, exist_ok=True)
    dat.write_bytes(b"not a real ANLZ file")
    contents = [
        _content("/Contents/a.wav", analysis_data_file_path="/PIONEER/USBANLZ/a/ANLZ0000.DAT")
    ]
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: ["/Contents/a.wav"]}, contents)
    calls: list[SyncProgress] = []

    sync_playlists(library, [1], on_progress=calls.append)

    analysis = [sample for sample in calls if sample.phase == "analysis"]
    assert len(analysis) == 1
    assert (analysis[0].done, analysis[0].total, analysis[0].item) == (1, 1, "/Contents/a.wav")
    assert analysis[0].error is not None


def test_on_progress_skips_analysis_when_nothing_has_analysis_data(tmp_path: Path) -> None:
    """No ANLZ data means no analysis samples; crate writes still report."""
    mount = _stick(tmp_path, indexed=["Contents/a.mp3"])
    playlist = Playlist(id=1, name="test", parent_id=None, is_folder=False)
    library = _library(mount, [playlist], {1: ["/Contents/a.mp3"]}, [_content("/Contents/a.mp3")])
    calls: list[SyncProgress] = []

    sync_playlists(library, [1], on_progress=calls.append)

    assert [sample.phase for sample in calls] == ["crates"]
    assert calls[0] == SyncProgress("crates", 1, 1, "test")
