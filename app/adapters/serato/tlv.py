"""Encoding for Serato's tag/length/value container format.

`database V2` and `.crate` files are a flat stream of records:

    [ 4-byte ASCII tag ][ 4-byte big-endian length ][ payload ]

The first character of the tag determines how the payload is encoded.
"""

from __future__ import annotations

import struct

TlvValue = str | int | bool | list[tuple[str, "TlvValue"]]


class SeratoEncodingError(ValueError):
    """Raised when a field cannot be encoded for a Serato container."""


def encode_field(tag: str, value: TlvValue) -> bytes:
    """
    Encode one tagged field.

    Args:
        tag: Four-character Serato field tag.
        value: Value matching the type implied by the tag prefix.

    Returns:
        Encoded tag, length, and payload bytes.

    Raises:
        SeratoEncodingError: Tag is malformed or the value does not match it.
    """
    if len(tag) != 4:
        raise SeratoEncodingError(f"Serato tags are 4 characters: {tag!r}")

    kind = tag[0]
    if kind == "o":
        if not isinstance(value, list):
            raise SeratoEncodingError(f"{tag}: container expects a list of fields")
        payload = encode_fields(value)
    elif kind in "vtp":
        if not isinstance(value, str):
            raise SeratoEncodingError(f"{tag}: expects a string")
        payload = value.encode("utf-16-be")
    elif kind == "u":
        payload = struct.pack(">I", int(value))
    elif kind == "s":
        payload = struct.pack(">H", int(value))
    elif kind == "b":
        payload = struct.pack(">B", 1 if value else 0)
    else:
        raise SeratoEncodingError(f"{tag}: unknown field kind {kind!r}")

    return tag.encode("ascii") + struct.pack(">I", len(payload)) + payload


def encode_fields(fields: list[tuple[str, TlvValue]]) -> bytes:
    """
    Encode an ordered list of tagged fields.

    Args:
        fields: (tag, value) pairs in the order they should appear.

    Returns:
        Concatenated encoded fields.
    """
    return b"".join(encode_field(tag, value) for tag, value in fields)
