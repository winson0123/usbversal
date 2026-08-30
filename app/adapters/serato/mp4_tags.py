"""Serato BeatGrid / Markers2 in MP4 / M4A freeform atoms."""

from __future__ import annotations

import base64
import hashlib
import re
import struct
from dataclasses import dataclass, field

from app.adapters.serato.markers import markers_id3_to_mp4, markers_mp4_to_id3
from app.adapters.serato.tags import (
    TagFormatError,
    _flac_b64_decode,
    _unwrap_flac_payload,
    _wrap_flac_payload,
)

_AAC_PRIME_SAMPLES = 2112
_ITUNSMPB = re.compile(rb"iTunSMPB.{0,32}([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})")

_SERATO_MEAN = b"com.serato.dj"
_B64_WRAP = 72
_DATA_UTF8 = 1
_MP4_ATOMS = {
    "Serato BeatGrid": "beatgrid",
    "Serato Markers2": "markersv2",
    "Serato Markers_": "markers",
}
_MP4_BY_ATOM = {atom: description for description, atom in _MP4_ATOMS.items()}
_MP4_WRAP = frozenset({"markers", "markersv2"})
_CONTAINERS = frozenset(
    {
        b"moov",
        b"trak",
        b"mdia",
        b"minf",
        b"stbl",
        b"udta",
        b"edts",
        b"dinf",
        b"mvex",
        b"moof",
        b"traf",
        b"ilst",
        b"----",
    }
)
_FULL_CONTAINERS = frozenset({b"meta"})
_HDLR_BODY = bytes(4) + b"mdir" + bytes(12) + b"\x00"


@dataclass
class _Box:
    """One MP4 box: a leaf, or a container of child boxes."""

    kind: bytes
    header: bytes
    body: bytes
    children: list[_Box] | None = field(default=None)


def is_mp4(data: bytes) -> bool:
    """
    Return whether ``data`` starts with an ``ftyp`` box.

    Args:
        data: Whole file contents.

    Returns:
        True for MP4 / M4A / similar ISO-BMFF files.
    """
    return len(data) >= 8 and data[4:8] == b"ftyp"


def read_mp4_geob(data: bytes) -> dict[str, bytes]:
    """
    Read Serato payloads from ``----:com.serato.dj`` atoms.

    Args:
        data: Whole MP4 / M4A file.

    Returns:
        Mapping of GEOB description to payload bytes.

    Raises:
        TagFormatError: The file has no ``moov`` or an atom is truncated.
    """
    moov = _require_moov(_parse_boxes(data, 0, len(data)))
    ilst = _find_ilst(moov)
    frames: dict[str, bytes] = {}
    if ilst is None or ilst.children is None:
        return frames
    for item in ilst.children:
        parsed = _read_freeform(item)
        if parsed is None:
            continue
        mean, name, raw = parsed
        if mean != _SERATO_MEAN:
            continue
        description = _MP4_BY_ATOM.get(name.decode("ascii", "replace"))
        if description is None:
            continue
        _decoded_name, payload = _unwrap_flac_payload(
            _flac_b64_decode(raw.decode("ascii", "replace"))
        )
        if description == "Serato Markers_":
            payload = markers_mp4_to_id3(payload)
        frames[description] = payload
    return frames


def m4a_encoder_delay_ms(data: bytes) -> int:
    """
    Return AAC encoder delay in milliseconds.

    Prefers the ``iTunSMPB`` delay field. When that atom is missing, uses
    the AAC LC priming length (2112 samples) and the ``mdhd`` timescale.

    Args:
        data: Whole M4A / MP4 file.

    Returns:
        Delay to subtract from Rekordbox times so Serato's timeline lines
        up with the first decoded sample. Zero when no timescale is found.
    """
    timescale = _mdhd_timescale(data)
    if timescale <= 0:
        return 0
    delay_samples = _AAC_PRIME_SAMPLES
    match = _ITUNSMPB.search(data)
    if match is not None:
        delay_samples = int(match.group(2), 16)
    return max(0, round(delay_samples * 1000 / timescale))


def _mdhd_timescale(data: bytes) -> int:
    """
    Return the first ``mdhd`` timescale, or 0 when the box is missing.

    Args:
        data: Whole MP4 / M4A file.

    Returns:
        Samples per second stored in ``mdhd``.
    """
    offset = 0
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        if size < 8:
            return 0
        if kind == b"mdhd" and offset + 24 <= len(data):
            version = data[offset + 8]
            if version == 1 and offset + 32 <= len(data):
                return int.from_bytes(data[offset + 28 : offset + 32], "big")
            return int.from_bytes(data[offset + 20 : offset + 24], "big")
        if kind in _CONTAINERS or kind == b"moov":
            found = _mdhd_timescale(data[offset + 8 : offset + size])
            if found:
                return found
            offset += size
            continue
        offset += size if size > 0 else 8
    return 0


def write_mp4_bytes(data: bytes, updates: dict[str, bytes], dropped: set[str]) -> bytes:
    """
    Rebuild an MP4 / M4A file with updated Serato freeform atoms.

    ``mdat`` payload bytes stay identical. Chunk offsets are rewritten when
    ``moov`` changes size so samples still point at that payload.

    Args:
        data: Original file contents.
        updates: GEOB description to new payload.
        dropped: GEOB descriptions to delete.

    Returns:
        Rebuilt file bytes.

    Raises:
        TagFormatError: The file has no ``moov`` / ``mdat``, or a box is invalid.
    """
    boxes = _parse_boxes(data, 0, len(data))
    moov = _require_moov(boxes)
    old_mdat = _mdat_payload_offset(boxes)
    ilst = _ensure_ilst(moov)
    if ilst.children is None:
        raise TagFormatError("MP4 ilst is not a container")
    ilst.children = _rewritten_ilst(ilst.children, updates, dropped)
    new_mdat = _mdat_payload_offset(boxes)
    _adjust_chunk_offsets(boxes, old_mdat, new_mdat)
    return b"".join(_serialize(box) for box in boxes)


def mdat_payload(data: bytes) -> bytes:
    """
    Return the first ``mdat`` payload (the audio bitstream).

    Args:
        data: Whole MP4 / M4A file.

    Returns:
        Bytes inside the ``mdat`` box, not including its header.

    Raises:
        TagFormatError: No ``mdat`` box is present.
    """
    for box in _parse_boxes(data, 0, len(data)):
        if box.kind == b"mdat":
            return box.body
    raise TagFormatError("MP4 file has no mdat box")


def verify_mp4_rewrite(
    original: bytes,
    rebuilt: bytes,
    updates: dict[str, bytes],
    remove_geob: set[str],
) -> None:
    """
    Confirm an MP4 rewrite kept ``mdat`` and the requested atoms took.

    Args:
        original: File contents before the rewrite.
        rebuilt: File contents about to be written.
        updates: GEOB description to the payload it was supposed to become.
        remove_geob: GEOB descriptions that were supposed to be deleted.

    Raises:
        TagFormatError: Audio changed, or a frame is wrong.
    """
    original_hash = hashlib.sha256(mdat_payload(original)).digest()
    rebuilt_hash = hashlib.sha256(mdat_payload(rebuilt)).digest()
    if original_hash != rebuilt_hash:
        raise TagFormatError("Write would alter the audio stream")
    frames = read_mp4_geob(rebuilt)
    for description, payload in updates.items():
        if frames.get(description) != payload:
            raise TagFormatError(f"{description!r} did not read back as written")
    for description in remove_geob:
        if description in frames:
            raise TagFormatError(f"{description!r} was supposed to be removed")


def _require_moov(boxes: list[_Box]) -> _Box:
    """
    Return the ``moov`` box or raise.

    Args:
        boxes: Top-level boxes.

    Returns:
        The movie box.
    """
    moov = next((box for box in boxes if box.kind == b"moov"), None)
    if moov is None:
        raise TagFormatError("MP4 file has no moov box")
    return moov


def _parse_boxes(data: bytes, start: int, end: int) -> list[_Box]:
    """
    Parse sibling MP4 boxes in ``data[start:end]``.

    Args:
        data: File or parent payload.
        start: Inclusive offset.
        end: Exclusive offset.

    Returns:
        Boxes in file order.

    Raises:
        TagFormatError: A size field overruns the range.
    """
    boxes: list[_Box] = []
    offset = start
    while offset + 8 <= end:
        size = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        header_len = 8
        if size == 1:
            if offset + 16 > end:
                raise TagFormatError("Truncated MP4 largesize box")
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
            header_len = 16
        elif size == 0:
            size = end - offset
        if size < header_len or offset + size > end:
            raise TagFormatError(f"Invalid MP4 box {kind!r}")
        payload = data[offset + header_len : offset + size]
        boxes.append(_parse_box(kind, payload))
        offset += size
    return boxes


def _parse_box(kind: bytes, payload: bytes) -> _Box:
    """
    Build one box, descending into known containers.

    Args:
        kind: Four-byte box type.
        payload: Bytes after the size/type (and largesize) header.

    Returns:
        A leaf or a container with children.
    """
    if kind in _FULL_CONTAINERS:
        if len(payload) < 4:
            raise TagFormatError("Truncated MP4 meta box")
        return _Box(kind, payload[:4], b"", _parse_boxes(payload, 4, len(payload)))
    if kind in _CONTAINERS:
        return _Box(kind, b"", b"", _parse_boxes(payload, 0, len(payload)))
    return _Box(kind, b"", payload, None)


def _serialize(box: _Box) -> bytes:
    """
    Encode one box, including its children.

    Args:
        box: Box to write.

    Returns:
        Size, type, optional largesize, and payload.
    """
    payload = box.header + (
        box.body if box.children is None else b"".join(_serialize(child) for child in box.children)
    )
    total = 8 + len(payload)
    if total > 0xFFFFFFFF:
        return struct.pack(">I", 1) + box.kind + struct.pack(">Q", total + 8) + payload
    return struct.pack(">I", total) + box.kind + payload


def _serialized_size(box: _Box) -> int:
    """
    Return how many bytes ``_serialize`` would write for ``box``.

    Args:
        box: Box to measure.

    Returns:
        On-disk size including the header.
    """
    if box.children is None:
        payload_len = len(box.header) + len(box.body)
    else:
        payload_len = len(box.header) + sum(_serialized_size(child) for child in box.children)
    total = 8 + payload_len
    return total + 8 if total > 0xFFFFFFFF else total


def _mdat_payload_offset(boxes: list[_Box]) -> int:
    """
    Return the file offset of the first ``mdat`` payload.

    Args:
        boxes: Top-level boxes.

    Returns:
        Offset of the first audio byte.

    Raises:
        TagFormatError: No ``mdat`` box is present.
    """
    offset = 0
    for box in boxes:
        if box.kind == b"mdat":
            header = 16 if _serialized_size(box) > 0xFFFFFFFF else 8
            return offset + header
        offset += _serialized_size(box)
    raise TagFormatError("MP4 file has no mdat box")


def _child(box: _Box, kind: bytes) -> _Box | None:
    """
    Return the first child of ``kind``, if any.

    Args:
        box: Container to search.
        kind: Four-byte type.

    Returns:
        The child, or None.
    """
    if box.children is None:
        return None
    return next((child for child in box.children if child.kind == kind), None)


def _find_ilst(moov: _Box) -> _Box | None:
    """
    Return ``ilst`` under ``udta/meta`` or ``meta``.

    Args:
        moov: Movie box.

    Returns:
        The item list, or None when the file has no tags yet.
    """
    udta = _child(moov, b"udta")
    if udta is not None:
        meta = _child(udta, b"meta")
        if meta is not None:
            found = _child(meta, b"ilst")
            if found is not None:
                return found
    meta = _child(moov, b"meta")
    if meta is None:
        return None
    return _child(meta, b"ilst")


def _ensure_ilst(moov: _Box) -> _Box:
    """
    Return ``ilst``, creating ``udta/meta/ilst`` when the file has none.

    Args:
        moov: Movie box.

    Returns:
        The item list to edit.

    Raises:
        TagFormatError: ``moov`` is not a container.
    """
    existing = _find_ilst(moov)
    if existing is not None:
        return existing
    if moov.children is None:
        raise TagFormatError("MP4 moov is not a container")
    udta = _child(moov, b"udta")
    if udta is None:
        udta = _Box(b"udta", b"", b"", [])
        moov.children.append(udta)
    if udta.children is None:
        raise TagFormatError("MP4 udta is not a container")
    meta = _child(udta, b"meta")
    if meta is None:
        meta = _Box(
            b"meta",
            b"\x00\x00\x00\x00",
            b"",
            [_Box(b"hdlr", b"", _HDLR_BODY, None)],
        )
        udta.children.append(meta)
    if meta.children is None:
        raise TagFormatError("MP4 meta is not a container")
    ilst = _child(meta, b"ilst")
    if ilst is None:
        ilst = _Box(b"ilst", b"", b"", [])
        meta.children.append(ilst)
    return ilst


def _atom_text(box: _Box) -> bytes:
    """
    Return the string payload of a ``mean`` or ``name`` box.

    Args:
        box: Leaf whose body starts with a 4-byte FullBox header.

    Returns:
        The identifier bytes.

    Raises:
        TagFormatError: The box is shorter than the header.
    """
    if len(box.body) < 4:
        raise TagFormatError("Truncated MP4 freeform atom")
    return box.body[4:]


def _data_payload(box: _Box) -> bytes:
    """
    Return the payload of a ``data`` box (after type and locale).

    Args:
        box: ``data`` leaf.

    Returns:
        Stored bytes (base64 text for Serato atoms).

    Raises:
        TagFormatError: The box is shorter than the 8-byte prefix.
    """
    if len(box.body) < 8:
        raise TagFormatError("Truncated MP4 data atom")
    return box.body[8:]


def _read_freeform(item: _Box) -> tuple[bytes, bytes, bytes] | None:
    """
    Read ``mean``, ``name``, and ``data`` from one ``----`` item.

    Args:
        item: An ``ilst`` child.

    Returns:
        ``(mean, name, data)`` or None when this is not a complete freeform item.
    """
    if item.kind != b"----" or item.children is None:
        return None
    mean = name = data = None
    for child in item.children:
        if child.kind == b"mean":
            mean = _atom_text(child)
        elif child.kind == b"name":
            name = _atom_text(child)
        elif child.kind == b"data":
            data = _data_payload(child)
    if mean is None or name is None or data is None:
        return None
    return mean, name, data


def _b64_encode(payload: bytes, *, wrap: bool) -> bytes:
    """
    Encode a Serato MP4 field: base64, no padding, optional 72-char wraps.

    Args:
        payload: Bytes after the ``application/octet-stream`` wrapper.
        wrap: Insert a newline every 72 characters (``markers`` / ``markersv2``).

    Returns:
        ASCII base64 ready for the ``data`` atom.
    """
    encoded = base64.b64encode(payload).decode("ascii").rstrip("=")
    if wrap:
        encoded = "\n".join(
            encoded[index : index + _B64_WRAP] for index in range(0, len(encoded), _B64_WRAP)
        )
    return encoded.encode("ascii")


def _freeform_item(atom_name: str, description: str, payload: bytes) -> _Box:
    """
    Build one ``----:com.serato.dj`` item.

    Args:
        atom_name: Freeform name (``beatgrid``, ``markersv2``, …).
        description: GEOB description stored inside the wrapper.
        payload: The same bytes ID3 GEOB would carry.

    Returns:
        An ``----`` box ready to sit in ``ilst``.
    """
    if description == "Serato Markers_":
        payload = markers_id3_to_mp4(payload)
    raw = _b64_encode(_wrap_flac_payload(description, payload), wrap=atom_name in _MP4_WRAP)
    return _Box(
        b"----",
        b"",
        b"",
        [
            _Box(b"mean", b"", b"\x00\x00\x00\x00" + _SERATO_MEAN, None),
            _Box(b"name", b"", b"\x00\x00\x00\x00" + atom_name.encode("ascii"), None),
            _Box(b"data", b"", struct.pack(">II", _DATA_UTF8, 0) + raw, None),
        ],
    )


def _rewritten_ilst(
    children: list[_Box],
    updates: dict[str, bytes],
    dropped: set[str],
) -> list[_Box]:
    """
    Replace or drop Serato atoms; leave every other ``ilst`` item untouched.

    Args:
        children: Current ``ilst`` items.
        updates: GEOB description to new payload.
        dropped: GEOB descriptions to delete.

    Returns:
        New ``ilst`` children.
    """
    drop_atoms = {_MP4_ATOMS[name] for name in dropped if name in _MP4_ATOMS}
    replace = {_MP4_ATOMS[name]: name for name in updates if name in _MP4_ATOMS}
    kept: list[_Box] = []
    written: set[str] = set()
    for item in children:
        parsed = _read_freeform(item)
        if parsed is None:
            kept.append(item)
            continue
        mean, name, _raw = parsed
        atom = name.decode("ascii", "replace")
        if mean == _SERATO_MEAN and atom in drop_atoms:
            continue
        description = replace.get(atom) if mean == _SERATO_MEAN else None
        if description is not None:
            kept.append(_freeform_item(atom, description, updates[description]))
            written.add(description)
            continue
        kept.append(item)
    for description, payload in updates.items():
        if description in written or description not in _MP4_ATOMS:
            continue
        kept.append(_freeform_item(_MP4_ATOMS[description], description, payload))
    return kept


def _walk(boxes: list[_Box]) -> list[_Box]:
    """
    Return ``boxes`` and every descendant, depth-first.

    Args:
        boxes: Roots to walk.

    Returns:
        Flattened boxes.
    """
    found: list[_Box] = []
    for box in boxes:
        found.append(box)
        if box.children is not None:
            found.extend(_walk(box.children))
    return found


def _adjust_chunk_offsets(boxes: list[_Box], old_mdat: int, new_mdat: int) -> None:
    """
    Add ``new_mdat - old_mdat`` to sample offsets that pointed at or past ``mdat``.

    Args:
        boxes: Top-level boxes (``stco`` / ``co64`` live under ``moov``).
        old_mdat: Payload offset before the rewrite.
        new_mdat: Payload offset after ``ilst`` changed size.
    """
    delta = new_mdat - old_mdat
    if delta == 0:
        return
    for box in _walk(boxes):
        if box.kind == b"stco":
            box.body = _shift_offsets(box.body, 4, delta, old_mdat)
        elif box.kind == b"co64":
            box.body = _shift_offsets(box.body, 8, delta, old_mdat)


def _shift_offsets(body: bytes, width: int, delta: int, threshold: int) -> bytes:
    """
    Add ``delta`` to each chunk offset that is at least ``threshold``.

    Args:
        body: ``stco`` / ``co64`` payload (FullBox header + count + entries).
        width: 4 for ``stco``, 8 for ``co64``.
        delta: Bytes the ``mdat`` payload moved.
        threshold: Old ``mdat`` payload offset.

    Returns:
        Updated payload.

    Raises:
        TagFormatError: The table is truncated or an offset no longer fits.
    """
    if len(body) < 8:
        raise TagFormatError("Truncated MP4 chunk-offset box")
    count = int.from_bytes(body[4:8], "big")
    out = bytearray(body)
    for index in range(count):
        pos = 8 + index * width
        if pos + width > len(out):
            raise TagFormatError("Truncated MP4 chunk-offset table")
        offset = int.from_bytes(out[pos : pos + width], "big")
        if offset < threshold:
            continue
        moved = offset + delta
        if moved < 0 or moved >= 1 << (width * 8):
            raise TagFormatError("MP4 chunk offset does not fit")
        out[pos : pos + width] = moved.to_bytes(width, "big")
    return bytes(out)
