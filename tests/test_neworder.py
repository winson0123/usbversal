"""Tests for crate display order in neworder.pref."""

from app.adapters.serato.neworder import with_ancestors, with_parent_first


def test_with_ancestors_inserts_folder_stems_before_each_leaf() -> None:
    """Serato needs Gigs and Gigs%%Played in neworder even without those files."""
    assert with_ancestors(
        [
            "MY_USB",
            "MY_USB%%Gigs%%pocket 29aug2026",
            "MY_USB%%Gigs%%Played%%pocket 25oct2025",
        ]
    ) == [
        "MY_USB",
        "MY_USB%%Gigs",
        "MY_USB%%Gigs%%pocket 29aug2026",
        "MY_USB%%Gigs%%Played",
        "MY_USB%%Gigs%%Played%%pocket 25oct2025",
    ]


def test_with_ancestors_is_idempotent() -> None:
    """A second pass must not duplicate folder stems."""
    once = with_ancestors(["MY_USB%%Gigs%%Played%%pocket"])
    assert with_ancestors(once) == once


def test_with_parent_first_then_ancestors_keeps_volume_on_top() -> None:
    """The thumbdrive folder stays first after ancestors are filled in."""
    order = with_ancestors(with_parent_first(["MY_USB%%Gigs%%pocket"], "MY_USB"))
    assert order[0] == "MY_USB"
    assert "MY_USB%%Gigs" in order
