"""Tests for cross-vendor path normalization."""

from app.core.track_paths import build_serato_path_index, normalize_track_path


def test_normalize_track_path() -> None:
    """normalize_track_path strips slashes and lowercases."""
    assert normalize_track_path("/Contents/A/track.mp3") == "contents/a/track.mp3"
    assert normalize_track_path("Contents\\A\\track.mp3") == "contents/a/track.mp3"


def test_build_serato_path_index() -> None:
    """build_serato_path_index maps normalized keys to canonical Serato paths."""
    index = build_serato_path_index(
        ["Contents/Artist/track.mp3", "/Contents/OTHER/other.mp3"],
    )
    assert index["contents/artist/track.mp3"] == "Contents/Artist/track.mp3"
    assert index["contents/other/other.mp3"] == "/Contents/OTHER/other.mp3"
