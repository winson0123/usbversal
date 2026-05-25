"""Tests for Rekordbox to Camelot key mapping."""

from app.core.key_notation import rekordbox_key_to_camelot


def test_rekordbox_key_to_camelot_major_minor() -> None:
    """Common Rekordbox keys map to Serato Camelot codes."""
    assert rekordbox_key_to_camelot("B") == "1B"
    assert rekordbox_key_to_camelot("Bm") == "1A"
    assert rekordbox_key_to_camelot("F#") == "2B"
    assert rekordbox_key_to_camelot("Ab") == "4B"


def test_rekordbox_key_to_camelot_passthrough() -> None:
    """USB export may already use Camelot codes."""
    assert rekordbox_key_to_camelot("8B") == "8B"
    assert rekordbox_key_to_camelot("12A") == "12A"


def test_rekordbox_key_to_camelot_unknown() -> None:
    """Unknown keys return None."""
    assert rekordbox_key_to_camelot("not-a-key") is None
    assert rekordbox_key_to_camelot(None) is None
