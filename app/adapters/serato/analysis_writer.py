"""Write Serato analysis tags into audio files (ID3 GEOB)."""

from __future__ import annotations

from pathlib import Path

import structlog
from mutagen.id3 import ID3, TBPM, TKEY
from serato_tools.track_autotags import TrackAutotags
from serato_tools.track_beatgrid import TrackBeatgrid
from serato_tools.track_cues_v2 import TrackCuesV2

from app.adapters.base import WriteContext
from app.adapters.rekordbox.analysis import RekordboxHotCue, RekordboxTrackAnalysis

logger = structlog.get_logger(__name__)

_DEFAULT_CUE_FIELD1 = b"\x00"
_DEFAULT_CUE_FIELD4 = b"\x00"
_DEFAULT_CUE_FIELD6 = b"\x00\x00"
_DEFAULT_CUE_COLOR = TrackCuesV2.CueColors.RED.value


def _build_serato_beatgrid(analysis: RekordboxTrackAnalysis) -> TrackBeatgrid.EntryList | None:
    """
    Build a sparse Serato beatgrid from Rekordbox ANLZ beat anchors.

    Args:
        analysis: Rekordbox track analysis.

    Returns:
        Serato beatgrid entry tuple or None when BPM is unknown.
    """
    bpm = analysis.beatgrid_bpm or analysis.bpm
    if bpm is None or bpm <= 0:
        return None
    first_s = (analysis.first_beat_ms or 0) / 1000.0
    terminal_s = first_s + 120.0
    return (
        TrackBeatgrid.NonTerminalBeatgridMarker(first_s, 4),
        TrackBeatgrid.TerminalBeatgridMarker(terminal_s, float(bpm)),
        TrackBeatgrid.Footer(0),
    )


def _build_cue_entries(hot_cues: tuple[RekordboxHotCue, ...]) -> list[TrackCuesV2.Entry]:
    """
    Map Rekordbox hot cues to Serato Markers2 cue/loop entries.

    Args:
        hot_cues: Rekordbox hot cue list.

    Returns:
        Serato Markers2 entry list (may be empty).
    """
    entries: list[TrackCuesV2.Entry] = []
    for cue in hot_cues:
        if cue.is_loop and cue.loop_end_ms is not None:
            entries.append(
                TrackCuesV2.LoopEntry(
                    field1=_DEFAULT_CUE_FIELD1,
                    index=cue.index,
                    startposition=cue.position_ms,
                    endposition=cue.loop_end_ms,
                    field5=b"\x00\x00\x00\x00",
                    field6=b"\x00\x00\x00\x00",
                    color=_DEFAULT_CUE_COLOR,
                    locked=False,
                    name="",
                ),
            )
        else:
            entries.append(
                TrackCuesV2.CueEntry(
                    field1=_DEFAULT_CUE_FIELD1,
                    index=cue.index,
                    position=cue.position_ms,
                    field4=_DEFAULT_CUE_FIELD4,
                    color=_DEFAULT_CUE_COLOR,
                    field6=_DEFAULT_CUE_FIELD6,
                    name="",
                ),
            )
    return entries


def write_serato_analysis_to_mp3(
    mp3_path: Path,
    analysis: RekordboxTrackAnalysis,
    write_context: WriteContext,
) -> list[str]:
    """
    Write Serato-compatible analysis tags into an MP3 file.

    Updates GEOB Serato Autotags, BeatGrid, Markers2 and standard TBPM/TKEY frames.
    Does not generate waveform overview data (requires separate binary encode).

    Args:
        mp3_path: Absolute path to the audio file on the mount.
        analysis: Rekordbox analysis to copy.
        write_context: Validated backup directory (required before write).

    Returns:
        List of human-readable fields written (e.g. "bpm", "key", "cues").

    Raises:
        ValueError: If mp3_path is not a file.
        OSError: On tag save failure.
    """
    _ = write_context
    if not mp3_path.is_file():
        raise ValueError(f"MP3 not found: {mp3_path}")

    written: list[str] = []

    if analysis.bpm is not None:
        autotags = TrackAutotags(str(mp3_path))
        autogain = autotags.autogain if autotags.autogain is not None else 0.0
        gaindb = autotags.gaindb if autotags.gaindb is not None else 0.0
        autotags.set(bpm=float(analysis.bpm), autogain=autogain, gaindb=gaindb)
        autotags.save()
        written.append("bpm")

    grid_entries = _build_serato_beatgrid(analysis)
    if grid_entries is not None:
        beatgrid = TrackBeatgrid(str(mp3_path))
        beatgrid.entries = grid_entries
        beatgrid._dump()
        beatgrid.save()
        written.append("beatgrid")

    cue_entries = _build_cue_entries(analysis.hot_cues)
    if cue_entries:
        cues = TrackCuesV2(str(mp3_path))
        cues.entries = cue_entries
        cues._dump()
        cues.modified = True
        cues.save(force=True)
        written.append(f"cues:{len(cue_entries)}")

    if analysis.camelot_key:
        tags = ID3(str(mp3_path))
        tags["TKEY"] = TKEY(encoding=3, text=analysis.camelot_key)
        if analysis.bpm is not None:
            tags["TBPM"] = TBPM(encoding=3, text=f"{analysis.bpm:.3f}")
        tags.save(mp3_path)
        written.append("key")

    logger.info(
        "serato_analysis_written",
        path=str(mp3_path),
        fields=written,
        content_id=analysis.content_id,
    )
    return written
