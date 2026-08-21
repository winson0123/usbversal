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


def crate_name_for(playlist: Playlist) -> str:
    """
    Return the crate filename stem a playlist maps to.

    Sync state and the crate writer must agree on this mapping, so both call
    here rather than deriving names independently.

    Args:
        playlist: Rekordbox playlist node.

    Returns:
        Crate filename stem, without the .crate extension.
    """
    return sanitize_crate_name(playlist.name)
