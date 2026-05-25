"""Musical key notation helpers (Rekordbox -> Serato Camelot TKEY)."""

from __future__ import annotations

import re

_CAMELOT_PATTERN = re.compile(r"^(\d{1,2})([AB])$", re.IGNORECASE)

# Rekordbox `Key.name` values observed on exportLibrary.db -> Serato Open Key / Camelot.
# Serato stores this in the ID3 TKEY frame (e.g. "8B", "4A").
REKORDBOX_KEY_TO_CAMELOT: dict[str, str] = {
    "Ab": "4B",
    "Abm": "4A",
    "A": "11B",
    "Am": "11A",
    "Bb": "6B",
    "Bbm": "6A",
    "B": "1B",
    "Bm": "1A",
    "C": "8B",
    "Cm": "8A",
    "Db": "3B",
    "Dbm": "3A",
    "D": "10B",
    "Dm": "10A",
    "Eb": "5B",
    "Ebm": "5A",
    "E": "12B",
    "Em": "12A",
    "F": "7B",
    "Fm": "7A",
    "F#": "2B",
    "F#m": "2A",
    "Gb": "2B",
    "Gbm": "2A",
    "G": "9B",
    "Gm": "9A",
}


def _is_camelot_notation(key_name: str) -> bool:
    """
    Return True when the key name is already Open Key / Camelot (e.g. 8B, 12A).

    Args:
        key_name: Trimmed key label.

    Returns:
        True if the value matches Camelot pattern.
    """
    return _CAMELOT_PATTERN.fullmatch(key_name) is not None


def rekordbox_key_to_camelot(key_name: str | None) -> str | None:
    """
    Convert a Rekordbox key label to Serato Camelot notation.

    USB exports often store Camelot codes directly in `Key.name`. Desktop
    libraries may use traditional names (Bm, F#) which are mapped via the table.

    Args:
        key_name: Rekordbox Key.name (e.g. "Bm", "F#", or "8B").

    Returns:
        Camelot code for TKEY (e.g. "1A") or None if unknown.
    """
    if not key_name:
        return None
    name = key_name.strip()
    if match := _CAMELOT_PATTERN.fullmatch(name):
        return f"{match.group(1)}{match.group(2).upper()}"
    return REKORDBOX_KEY_TO_CAMELOT.get(name)
