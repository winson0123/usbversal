"""Mapping Rekordbox playlists to Serato crate filenames."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.domain import Playlist

# Windows forbids these in a filename. "/" is special-cased: a real slash
# cannot live in the .crate name, but "_" was losing the character the user
# typed. Division slash (U+2215) is legal on exFAT and looks like "/".
# Fullwidth solidus was the TASK-254 stand-in; it renders as "／" in Serato.
_INVALID_CRATE_CHARS = re.compile(r'[<>:"\\|?*]')
_SLASH = "/"
_SLASH_STAND_IN = "\u2215"
_LEGACY_SLASH_STAND_IN = "\uff0f"


def volume_label_for(mount: Path) -> str:
    """
    Return the Serato parent-crate name for a USB mount.

    Uses the mount folder name, which is the volume label on Linux
    (``/media/$USER/WONSIN``) and macOS (``/Volumes/WONSIN``). A path with
    no folder name (a bare drive letter) becomes ``USB``.

    Args:
        mount: Mount root of the stick.

    Returns:
        Sanitized crate-name segment for the volume parent.
    """
    name = mount.resolve().name.strip()
    return sanitize_crate_name(name) if name else "USB"


def sanitize_crate_name(name: str) -> str:
    """
    Convert a playlist name into a safe Serato crate filename stem.

    A ``/`` in the Rekordbox name becomes a division slash (U+2215) so the
    crate still reads as a slash. Other characters Windows rejects become
    ``_``.

    Args:
        name: Rekordbox playlist display name.

    Returns:
        Sanitized name without the .crate extension.
    """
    cleaned = name.strip().replace(_SLASH, _SLASH_STAND_IN)
    cleaned = _INVALID_CRATE_CHARS.sub("_", cleaned)
    cleaned = cleaned.strip(" .")
    return cleaned or "Untitled"


def crate_name_slash_aliases(stem: str) -> tuple[str, ...]:
    """
    Return this stem spelled with each slash stand-in.

    A re-sync after changing the stand-in must delete the old filename so
    Serato does not show both spellings.

    Args:
        stem: Crate filename stem.

    Returns:
        Unique stems, current spelling first.
    """
    current = stem.replace(_LEGACY_SLASH_STAND_IN, _SLASH_STAND_IN)
    legacy = stem.replace(_SLASH_STAND_IN, _LEGACY_SLASH_STAND_IN)
    if current == legacy:
        return (current,)
    return (current, legacy)


def drop_legacy_slash_names(order: list[str], current: list[str]) -> list[str]:
    """
    Remove crate names that are only an old slash spelling of ``current``.

    Args:
        order: Display order, possibly including leftover fullwidth names.
        current: Crate stems just written.

    Returns:
        Order without those leftovers.
    """
    keep = set(current)
    drop: set[str] = set()
    for name in current:
        for alias in crate_name_slash_aliases(name):
            if alias not in keep:
                drop.add(alias)
    return [name for name in order if name not in drop]


def crate_name_for(
    playlist: Playlist,
    by_id: dict[int, Playlist],
    volume: str | None = None,
) -> str:
    """
    Return the crate filename stem a playlist maps to.

    Serato's crate list is flat, so a nested Rekordbox folder is encoded into
    the filename: each ancestor folder's sanitized name, then the playlist's
    own, joined with "%%" -- "Techno / Peak Time" becomes
    "Techno%%Peak Time.crate". Confirmed in Serato (TASK-245): a synced
    Rekordbox ``Gigs / Played / safety day`` playlist appears under Played
    under Gigs. Rekordbox folder ancestors do not get their own empty
    ``.crate`` files.

    When ``volume`` is set, it is the outermost parent (the thumbdrive
    label). ``Contents`` on WONSIN becomes ``WONSIN%%Contents``. Sync also
    writes an empty ``WONSIN.crate`` so Serato has a real folder node.

    Sync state and the crate writer must agree on this mapping, so both call
    here rather than deriving names independently.

    Args:
        playlist: Rekordbox playlist node.
        by_id: Every playlist on the library, keyed by id, used to walk
            ancestor folders. A playlist whose parent chain is not fully
            present here (never observed, but not assumed impossible) stops
            at the last resolvable ancestor rather than raising.
        volume: Optional thumbdrive label prefixed as the crate parent.

    Returns:
        Crate filename stem, without the .crate extension.
    """
    names = [sanitize_crate_name(playlist.name)]
    seen = {playlist.id}
    parent_id = playlist.parent_id
    while parent_id is not None and parent_id not in seen:
        parent = by_id.get(parent_id)
        if parent is None:
            break
        names.append(sanitize_crate_name(parent.name))
        seen.add(parent_id)
        parent_id = parent.parent_id
    stem = "%%".join(reversed(names))
    if not volume:
        return stem
    return f"{sanitize_crate_name(volume)}%%{stem}"
