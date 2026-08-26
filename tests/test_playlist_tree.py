"""Tests for nesting a flat playlist list into a tree."""

from app.core.domain import Playlist
from app.core.playlist_tree import build_playlist_tree


def test_flat_playlists_are_all_roots() -> None:
    """No folders means every playlist sits at the top level."""
    playlists = [
        Playlist(id=1, name="A", parent_id=None, is_folder=False),
        Playlist(id=2, name="B", parent_id=None, is_folder=False),
    ]

    tree = build_playlist_tree(playlists)

    assert [node.playlist.name for node in tree] == ["A", "B"]
    assert all(node.children == () for node in tree)


def test_children_nest_under_their_folder() -> None:
    """A playlist referencing a folder's id becomes that folder's child."""
    playlists = [
        Playlist(id=9, name="Genres", parent_id=None, is_folder=True),
        Playlist(id=1, name="Techno", parent_id=9, is_folder=False),
        Playlist(id=2, name="Trance", parent_id=9, is_folder=False),
    ]

    (root,) = build_playlist_tree(playlists)

    assert root.playlist.name == "Genres"
    assert [child.playlist.name for child in root.children] == ["Techno", "Trance"]


def test_nesting_goes_arbitrarily_deep() -> None:
    """A folder inside a folder nests correctly at every level."""
    playlists = [
        Playlist(id=1, name="Root", parent_id=None, is_folder=True),
        Playlist(id=2, name="Mid", parent_id=1, is_folder=True),
        Playlist(id=3, name="Leaf", parent_id=2, is_folder=False),
    ]

    (root,) = build_playlist_tree(playlists)

    assert root.children[0].playlist.name == "Mid"
    assert root.children[0].children[0].playlist.name == "Leaf"


def test_sibling_order_is_preserved() -> None:
    """Children appear in the same order they were given in."""
    playlists = [
        Playlist(id=9, name="Folder", parent_id=None, is_folder=True),
        Playlist(id=3, name="Third", parent_id=9, is_folder=False),
        Playlist(id=1, name="First", parent_id=9, is_folder=False),
        Playlist(id=2, name="Second", parent_id=9, is_folder=False),
    ]

    (root,) = build_playlist_tree(playlists)

    assert [child.playlist.name for child in root.children] == ["Third", "First", "Second"]


def test_a_dangling_parent_reference_is_promoted_to_root() -> None:
    """A playlist whose declared parent is absent is not silently dropped."""
    playlists = [
        Playlist(id=1, name="Orphan", parent_id=999, is_folder=False),
    ]

    tree = build_playlist_tree(playlists)

    assert [node.playlist.name for node in tree] == ["Orphan"]


def test_empty_input_yields_an_empty_tree() -> None:
    """No playlists at all is a valid, empty tree."""
    assert build_playlist_tree([]) == ()
