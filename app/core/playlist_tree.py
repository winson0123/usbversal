"""Nesting a flat, parent_id-linked playlist list into a tree."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.domain import Playlist


@dataclass(frozen=True)
class PlaylistNode:
    """
    One node in a Rekordbox playlist tree, with its children nested.

    Attributes:
        playlist: The underlying playlist or folder.
        children: Nested playlist/folder nodes, in Rekordbox order.
    """

    playlist: Playlist
    children: tuple[PlaylistNode, ...] = ()


def build_playlist_tree(playlists: Sequence[Playlist]) -> tuple[PlaylistNode, ...]:
    """
    Nest a flat, parent_id-linked playlist list into a tree.

    Args:
        playlists: Flat playlist/folder list, in Rekordbox order.

    Returns:
        Root-level nodes, each with its descendants nested. Order is
        preserved within each level. A node whose declared parent is not
        itself in ``playlists`` is treated as a root rather than dropped, so
        a dangling reference never silently loses a playlist from the tree.
    """
    known_ids = {p.id for p in playlists}
    by_parent: dict[int | None, list[Playlist]] = {}
    for playlist in playlists:
        parent = playlist.parent_id if playlist.parent_id in known_ids else None
        by_parent.setdefault(parent, []).append(playlist)

    def _nest(parent_id: int | None) -> tuple[PlaylistNode, ...]:
        return tuple(
            PlaylistNode(playlist=playlist, children=_nest(playlist.id))
            for playlist in by_parent.get(parent_id, [])
        )

    return _nest(None)
