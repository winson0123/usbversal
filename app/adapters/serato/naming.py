"""Mapping Rekordbox playlists to Serato crate filenames."""

from __future__ import annotations

import re

from app.core.domain import Playlist

_INVALID_CRATE_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_crate_name(name: str) -> str:
    """
    Convert a playlist name into a safe Serato crate filename stem.

    Args:
        name: Rekordbox playlist display name.

    Returns:
        Sanitized name without the .crate extension.
    """
    cleaned = _INVALID_CRATE_CHARS.sub("_", name.strip())
    cleaned = cleaned.strip(" .")
    return cleaned or "Untitled"


def crate_name_for(playlist: Playlist, by_id: dict[int, Playlist]) -> str:
    """
    Return the crate filename stem a playlist maps to.

    Serato's crate list is flat, so a nested Rekordbox folder is encoded into
    the filename: each ancestor folder's sanitized name, then the playlist's
    own, joined with "%%" -- "Techno / Peak Time" becomes
    "Techno%%Peak Time.crate". This convention is documented in
    docs/schemas/serato-schema-notes.md as **assumed, not verified against
    real Serato** -- there was no nested-folder playlist in the stick used to
    validate the rest of the write path.

    Sync state and the crate writer must agree on this mapping, so both call
    here rather than deriving names independently.

    Args:
        playlist: Rekordbox playlist node.
        by_id: Every playlist on the library, keyed by id, used to walk
            ancestor folders. A playlist whose parent chain is not fully
            present here (never observed, but not assumed impossible) stops
            at the last resolvable ancestor rather than raising.

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
    return "%%".join(reversed(names))
