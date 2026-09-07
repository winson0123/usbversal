"""Persistent host-side cache of analysis-ported verdicts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.host import host_volume_dir

CACHE_VERSION = 1
CACHE_FILENAME = "analysis-cache.json"

Fingerprint = tuple[int, int]


def analysis_cache_path(mount: Path) -> Path:
    """
    Return the path to this volume's analysis-cache JSON file.

    Args:
        mount: USB mount root.

    Returns:
        Absolute path under ``host_volume_dir`` (file may not exist yet).
    """
    return host_volume_dir(mount) / CACHE_FILENAME


def fingerprint(path: Path | None) -> Fingerprint:
    """
    Return ``(size, mtime_ns)`` for ``path``, or ``(0, 0)`` when missing.

    Args:
        path: File to fingerprint, or None.

    Returns:
        Size and nanosecond mtime, or zeros when the file is absent.
    """
    if path is None:
        return (0, 0)
    try:
        stat = path.stat()
    except OSError:
        return (0, 0)
    return (stat.st_size, stat.st_mtime_ns)


def cache_key(dat_rel: str, audio_rel: str) -> str:
    """
    Return the disk-cache key for one track.

    Args:
        dat_rel: Mount-relative ANLZ ``.DAT`` path, or empty when none.
        audio_rel: Mount-relative audio path.

    Returns:
        Stable string key for the JSON ``tracks`` map.
    """
    return f"{dat_rel}|{audio_rel}"


def relative_to_mount(mount: Path, path: Path | None) -> str:
    """
    Return a POSIX path relative to ``mount``, or empty when ``path`` is None.

    Args:
        mount: Mount root.
        path: Absolute path under the mount, or None.

    Returns:
        Relative path string, or ``""``.
    """
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(mount.resolve()).as_posix()
    except (ValueError, OSError):
        return path.as_posix()


def load_analysis_cache(mount: Path) -> dict[str, dict[str, Any]]:
    """
    Load track entries from the host analysis cache.

    Missing, corrupt, or wrong-version files yield an empty map.

    Args:
        mount: USB mount root.

    Returns:
        Disk key to entry dict (``ported``, ``audio``, ``dat``, ``ext``).
    """
    path = analysis_cache_path(mount)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict) or raw.get("version") != CACHE_VERSION:
        return {}
    tracks = raw.get("tracks")
    if not isinstance(tracks, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, entry in tracks.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            continue
        if "ported" not in entry:
            continue
        out[key] = entry
    return out


def save_analysis_cache(mount: Path, entries: dict[str, dict[str, Any]]) -> None:
    """
    Atomically write the analysis cache for ``mount``.

    Args:
        mount: USB mount root.
        entries: Disk key to entry dicts to persist.
    """
    root = host_volume_dir(mount)
    root.mkdir(parents=True, exist_ok=True)
    target = root / CACHE_FILENAME
    temporary = root / f".{CACHE_FILENAME}.tmp"
    payload = {"version": CACHE_VERSION, "tracks": entries}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(target)


def entry_fingerprints_match(
    entry: dict[str, Any],
    *,
    audio: Fingerprint,
    dat: Fingerprint,
    ext: Fingerprint,
) -> bool:
    """
    Return whether ``entry`` still matches the live fingerprints.

    Args:
        entry: One cache entry from disk.
        audio: Live audio fingerprint.
        dat: Live DAT fingerprint.
        ext: Live EXT fingerprint.

    Returns:
        True when all three fingerprints match the stored lists.
    """
    return (
        _fp_equal(entry.get("audio"), audio)
        and _fp_equal(entry.get("dat"), dat)
        and _fp_equal(entry.get("ext"), ext)
    )


def make_entry(
    *,
    ported: bool,
    audio: Fingerprint,
    dat: Fingerprint,
    ext: Fingerprint,
) -> dict[str, Any]:
    """
    Build one cache entry for disk.

    Args:
        ported: Analysis-ported verdict.
        audio: Audio fingerprint.
        dat: DAT fingerprint.
        ext: EXT fingerprint.

    Returns:
        JSON-serializable entry dict.
    """
    return {
        "ported": bool(ported),
        "audio": list(audio),
        "dat": list(dat),
        "ext": list(ext),
    }


def _fp_equal(stored: Any, live: Fingerprint) -> bool:
    """
    Compare a stored fingerprint list to a live tuple.

    Args:
        stored: Value from JSON (expect two ints).
        live: Live ``(size, mtime_ns)``.

    Returns:
        True when both numbers match.
    """
    if not isinstance(stored, (list, tuple)) or len(stored) != 2:
        return False
    try:
        return int(stored[0]) == live[0] and int(stored[1]) == live[1]
    except (TypeError, ValueError):
        return False
