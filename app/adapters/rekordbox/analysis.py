"""Extract Rekordbox analysis metadata for Serato sync."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog
from rbox import OneLibrary
from rbox.anlz import Anlz

from app.core.key_notation import rekordbox_key_to_camelot

logger = structlog.get_logger(__name__)

_NO_LOOP = 4_294_967_295


@dataclass(frozen=True)
class RekordboxHotCue:
    """
    Hot cue from Rekordbox ANLZ CueList.

    Attributes:
        index: Hot cue slot (1-based in ANLZ; mapped to Serato 0-based).
        position_ms: Cue position in milliseconds.
        is_loop: True when cue_type indicates a loop cue.
        loop_end_ms: Loop end in ms when is_loop; else None.
    """

    index: int
    position_ms: int
    is_loop: bool = False
    loop_end_ms: int | None = None


@dataclass(frozen=True)
class RekordboxTrackAnalysis:
    """
    Analysis fields read from exportLibrary.db and USBANLZ.

    Attributes:
        content_id: Rekordbox content id.
        path: Rekordbox content.path value.
        bpm: Tempo from bpmx100 when present.
        camelot_key: Serato-style TKEY value derived from key_id.
        hot_cues: Hot cues from ANLZ when available.
        first_beat_ms: First beat grid anchor time in ms.
        beatgrid_bpm: Beat grid tempo from ANLZ beats.
        anlz_path: Resolved ANLZ .DAT path when present.
    """

    content_id: int
    path: str
    bpm: float | None
    camelot_key: str | None
    hot_cues: tuple[RekordboxHotCue, ...]
    first_beat_ms: int | None
    beatgrid_bpm: float | None
    anlz_path: Path | None


def _resolve_anlz_path(mount: Path, analysis_data_file_path: str | None) -> Path | None:
    """
    Resolve USBANLZ path relative to mount.

    Args:
        mount: USB mount root.
        analysis_data_file_path: content.analysis_data_file_path from rbox.

    Returns:
        Absolute path to ANLZ0000.DAT or None.
    """
    if not analysis_data_file_path:
        return None
    candidate = mount / analysis_data_file_path.lstrip("/")
    return candidate if candidate.is_file() else None


def read_track_analysis(
    db: OneLibrary,
    mount: Path,
    content: object,
    *,
    key_names: dict[int, str],
) -> RekordboxTrackAnalysis:
    """
    Read BPM, key, hot cues, and beat grid anchors for one content row.

    Args:
        db: Open OneLibrary database.
        mount: USB mount root.
        content: rbox Content row from get_playlist_contents.
        key_names: Map of key_id -> Key.name.

    Returns:
        RekordboxTrackAnalysis with extracted fields.
    """
    content_id = int(content.id)
    path = str(content.path)
    bpm = None
    if getattr(content, "bpmx100", None):
        bpm = int(content.bpmx100) / 100.0

    camelot = None
    key_id = getattr(content, "key_id", None)
    if key_id is not None:
        camelot = rekordbox_key_to_camelot(key_names.get(int(key_id)))

    anlz_path = _resolve_anlz_path(mount, getattr(content, "analysis_data_file_path", None))
    hot_cues: list[RekordboxHotCue] = []
    first_beat_ms: int | None = None
    beatgrid_bpm: float | None = None

    if anlz_path is not None:
        try:
            anlz = Anlz(anlz_path)
            cue_list = anlz.get_extended_hot_cues() or anlz.get_hot_cues()
            if cue_list and cue_list.cues:
                for cue in cue_list.cues:
                    loop_end = int(cue.loop_time)
                    is_loop = loop_end not in (-1, _NO_LOOP) and loop_end > int(cue.time)
                    hot_cues.append(
                        RekordboxHotCue(
                            index=max(0, int(cue.hot_cue) - 1),
                            position_ms=int(cue.time),
                            is_loop=is_loop,
                            loop_end_ms=loop_end if is_loop else None,
                        ),
                    )
            grid = anlz.get_beat_grid()
            if grid and grid.beats:
                first = grid.beats[0]
                first_beat_ms = int(first.time)
                beatgrid_bpm = int(first.tempo) / 100.0
        except OSError as exc:
            logger.warning("anlz_read_failed", path=str(anlz_path), error=str(exc))

    if bpm is None and beatgrid_bpm is not None:
        bpm = beatgrid_bpm

    return RekordboxTrackAnalysis(
        content_id=content_id,
        path=path,
        bpm=bpm,
        camelot_key=camelot,
        hot_cues=tuple(hot_cues),
        first_beat_ms=first_beat_ms,
        beatgrid_bpm=beatgrid_bpm,
        anlz_path=anlz_path,
    )


def build_key_name_map(db: OneLibrary) -> dict[int, str]:
    """
    Build key_id -> name lookup from exportLibrary.db.

    Args:
        db: Open OneLibrary instance.

    Returns:
        Dict mapping key id to display name.
    """
    return {int(key.id): str(key.name) for key in db.get_keys()}
