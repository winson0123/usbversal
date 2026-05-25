"""Cross-vendor track path normalization."""

from __future__ import annotations

from collections.abc import Iterable


def normalize_track_path(path: str) -> str:
    """
    Normalize a track path for Rekordbox/Serato comparison.

    Strips leading slashes, normalizes separators, and lowercases for matching.

    Args:
        path: Vendor path (e.g. /Contents/Artist/track.mp3 or Contents/...).

    Returns:
        Normalized path key suitable for index lookups.
    """
    normalized = path.replace("\\", "/").strip().strip("/")
    return normalized.lower()


def build_serato_path_index(track_paths: Iterable[str]) -> dict[str, str]:
    """
    Map normalized path keys to canonical Serato path strings.

    When multiple Serato entries normalize to the same key, the first wins.

    Args:
        track_paths: Raw paths from Serato database V2.

    Returns:
        Dict of normalized key -> Serato path as stored in the library.
    """
    index: dict[str, str] = {}
    for raw in track_paths:
        key = normalize_track_path(raw)
        if key not in index:
            index[key] = raw
    return index
