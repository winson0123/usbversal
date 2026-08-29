"""Tests for crate display order in neworder.pref."""

from app.adapters.serato.neworder import with_ancestors, with_parent_first


def test_with_ancestors_inserts_folder_stems_before_each_leaf() -> None:
    """Serato needs Gigs and Gigs%%Played in neworder even without those files."""
    assert with_ancestors(
        [
            "WONSIN",
            "WONSIN%%Gigs%%pocket 29aug2026",
            "WONSIN%%Gigs%%Played%%pocket 25oct2025",
        ]
    ) == [
        "WONSIN",
        "WONSIN%%Gigs",
        "WONSIN%%Gigs%%pocket 29aug2026",
        "WONSIN%%Gigs%%Played",
        "WONSIN%%Gigs%%Played%%pocket 25oct2025",
    ]


def test_with_ancestors_is_idempotent() -> None:
    """A second pass must not duplicate folder stems."""
    once = with_ancestors(["WONSIN%%Gigs%%Played%%pocket"])
    assert with_ancestors(once) == once


def test_with_parent_first_then_ancestors_keeps_volume_on_top() -> None:
    """The thumbdrive folder stays first after ancestors are filled in."""
    order = with_ancestors(with_parent_first(["WONSIN%%Gigs%%pocket"], "WONSIN"))
    assert order[0] == "WONSIN"
    assert "WONSIN%%Gigs" in order
