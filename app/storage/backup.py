"""Backup copy utilities and manifest handling."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from app.storage.audio_delta import (
    AudioDeltaError,
    encode_audio_delta,
    is_audio_backup_path,
)

logger = structlog.get_logger(__name__)

BackupProgressCallback = Callable[[int, int], None]

BACKUP_ROOT_ENV = "USBVERSAL_BACKUP_ROOT"
_KIND_FULL = "full"
_KIND_DELTA = "delta"
_VOLUME_KEY = re.compile(r"[^A-Za-z0-9._-]+")
_BACKUP_ID_NAME = re.compile(r"^\d{8}T\d{6}Z(?:-\d+)?$")
_OBJECTS = "objects"
_LATEST = "latest"


@dataclass(frozen=True)
class BackupFileEntry:
    """
    One file recorded in a backup manifest.

    Attributes:
        relative_path: Path relative to source mount root.
        sha256: Hex digest of the stored artifact (full copy or delta).
        size: Stored artifact size in bytes.
        kind: ``full`` for a byte-identical copy, ``delta`` for an audio
            tag-region snapshot.
        stored_as: Where the artifact lives. New writes use
            ``objects/<sha256>`` under the volume root. Older snapshots
            keep an in-directory path (``relative_path`` or ``*.delta``).
        original_sha256: Source file hash before the write, when known.
        original_size: Source file size before the write, when known.
    """

    relative_path: str
    sha256: str
    size: int
    kind: str = _KIND_FULL
    stored_as: str | None = None
    original_sha256: str | None = None
    original_size: int | None = None

    def artifact_path(self) -> str:
        """
        Return the stored-as path recorded on this entry.

        This is not always on-disk relative to the snapshot directory.
        Use ``resolve_artifact`` to open the file.

        Returns:
            ``stored_as`` when set, otherwise ``relative_path``.
        """
        return self.stored_as or self.relative_path


@dataclass(frozen=True)
class BackupManifest:
    """
    Manifest describing a point-in-time backup.

    Attributes:
        backup_id: Unique backup identifier (timestamp-based).
        created_at: ISO-8601 UTC creation time.
        source_mount: Absolute path to the source mount root.
        files: Backed-up file entries.
    """

    backup_id: str
    created_at: str
    source_mount: str
    files: tuple[BackupFileEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize manifest to a JSON-compatible dictionary.

        Returns:
            Dict suitable for json.dumps.
        """
        return {
            "backup_id": self.backup_id,
            "created_at": self.created_at,
            "source_mount": self.source_mount,
            "files": [asdict(entry) for entry in self.files],
        }

    def write(self, backup_dir: Path) -> Path:
        """
        Write manifest.json into the backup directory.

        Args:
            backup_dir: Directory containing copied files.

        Returns:
            Path to the written manifest file.
        """
        path = backup_dir / "manifest.json"
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, backup_dir: Path) -> BackupManifest:
        """
        Load manifest.json from a backup directory.

        Args:
            backup_dir: Directory containing manifest.json.

        Returns:
            Parsed BackupManifest instance.

        Raises:
            FileNotFoundError: If manifest.json is missing.
            ValueError: If manifest JSON is invalid.
        """
        path = backup_dir / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        files = tuple(
            BackupFileEntry(
                relative_path=str(item["relative_path"]),
                sha256=str(item["sha256"]),
                size=int(item["size"]),
                kind=str(item.get("kind", _KIND_FULL)),
                stored_as=(str(item["stored_as"]) if item.get("stored_as") else None),
                original_sha256=(
                    str(item["original_sha256"]) if item.get("original_sha256") else None
                ),
                original_size=(int(item["original_size"]) if item.get("original_size") else None),
            )
            for item in data.get("files", [])
        )
        return cls(
            backup_id=str(data["backup_id"]),
            created_at=str(data["created_at"]),
            source_mount=str(data["source_mount"]),
            files=files,
        )


@dataclass(frozen=True)
class BackupResult:
    """
    Outcome of a backup operation.

    Attributes:
        backup_id: Identifier matching manifest and directory name.
        backup_dir: Root directory holding copies and manifest.json.
        manifest: Written manifest metadata.
    """

    backup_id: str
    backup_dir: Path
    manifest: BackupManifest


def default_backup_root(mount: Path) -> Path:
    """
    Return the host directory where backups for ``mount`` are stored.

    Uses ``USBVERSAL_BACKUP_ROOT`` when set, otherwise the platform user-data
    directory. Never defaults to a folder on the USB.

    Args:
        mount: Mount root; its name namespaces backups from different sticks.

    Returns:
        Absolute backup parent directory (created by the caller as needed).
    """
    override = os.environ.get(BACKUP_ROOT_ENV)
    if override:
        base = Path(override)
    elif os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        base = base / "usbversal" / "backups"
    else:
        base = Path.home() / ".local/share/usbversal/backups"
    return (base / _volume_key(mount)).resolve()


def _volume_key(mount: Path) -> str:
    """
    Return a filesystem-safe directory name for a mount.

    Args:
        mount: Mount root.

    Returns:
        Label derived from the mount folder name.
    """
    name = mount.resolve().name.strip() or "usb"
    cleaned = _VOLUME_KEY.sub("_", name).strip("._")
    return cleaned or "usb"


def resolve_artifact(backup_dir: Path, entry: BackupFileEntry) -> Path:
    """
    Return the on-disk path of a manifest entry's stored artifact.

    Content-addressed objects live in ``<volume>/objects/<sha256>``.
    Legacy snapshots keep the file inside the timestamped directory.

    Args:
        backup_dir: Timestamped snapshot directory (contains manifest.json).
        entry: One row from that snapshot's manifest.

    Returns:
        Absolute path of the full copy or delta blob.
    """
    stored = entry.artifact_path()
    if stored.startswith(f"{_OBJECTS}/"):
        return backup_dir.parent / stored
    return backup_dir / stored


def _write_latest(root: Path, backup_id: str) -> None:
    """
    Point ``latest`` at this snapshot when the id is a timestamp.

    Args:
        root: Volume backup parent.
        backup_id: Directory name just written or reused.
    """
    if not _BACKUP_ID_NAME.match(backup_id):
        return
    (root / _LATEST).write_text(f"{backup_id}\n", encoding="utf-8")


def _put_object(objects: Path, data: bytes) -> str:
    """
    Store ``data`` under ``objects/<sha256>`` if it is not already there.

    Args:
        objects: Volume ``objects`` directory.
        data: Artifact bytes (full file or UVSD1 delta).

    Returns:
        Hex digest, also the object filename.
    """
    digest = hashlib.sha256(data).hexdigest()
    destination = objects / digest
    if destination.is_file():
        return digest
    objects.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    replaced = False
    try:
        temporary.write_bytes(data)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        replaced = True
    finally:
        if not replaced:
            temporary.unlink(missing_ok=True)
    return digest


def _put_object_file(objects: Path, source: Path) -> str:
    """
    Copy ``source`` into the object store when that hash is new.

    Args:
        objects: Volume ``objects`` directory.
        source: Live file on the mount.

    Returns:
        Hex digest of ``source``.
    """
    digest = sha256_file(source)
    destination = objects / digest
    if not destination.is_file():
        objects.mkdir(parents=True, exist_ok=True)
        atomic_copy_file(source, destination)
    return digest


def sha256_file(path: Path) -> str:
    """
    Compute SHA-256 hex digest of a file.

    Args:
        path: File to hash.

    Returns:
        Lowercase hex digest string.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_copy_file(source: Path, destination: Path) -> None:
    """
    Copy a file atomically via a temporary sibling file.

    Args:
        source: Existing source file path.
        destination: Target file path to create or replace.

    Raises:
        OSError: On copy or rename failure.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    replaced = False
    try:
        shutil.copy2(source, temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        replaced = True
    finally:
        if not replaced:
            temporary.unlink(missing_ok=True)


def _backup_sources(mount: Path, files: list[Path]) -> list[tuple[Path, str]]:
    """
    Resolve each backup source to an absolute path and mount-relative name.

    Args:
        mount: Mount root; relative paths in the manifest are from here.
        files: Absolute or mount-relative file paths to copy.

    Returns:
        ``(source, relative)`` pairs in the order given.

    Raises:
        FileNotFoundError: If a source file does not exist.
    """
    sources: list[tuple[Path, str]] = []
    for file_path in files:
        source = file_path.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Backup source not found: {source}")
        try:
            relative = source.relative_to(mount).as_posix()
        except ValueError:
            relative = source.name
        sources.append((source, relative))
    return sources


def _latest_backup_dir(root: Path) -> Path | None:
    """
    Return the newest timestamped backup directory under ``root``.

    Ignores ``pre-rollback-*`` snapshots and anything without a manifest.

    Args:
        root: Host backup parent for one volume.

    Returns:
        The latest backup directory, or None when none exist.
    """
    if not root.is_dir():
        return None
    candidates = [
        path
        for path in root.iterdir()
        if path.is_dir() and _BACKUP_ID_NAME.match(path.name) and (path / "manifest.json").is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.name)


def _source_matches_entry(source: Path, entry: BackupFileEntry) -> bool:
    """
    Return True when ``source`` is still the file this entry backed up.

    Args:
        source: Live file on the mount.
        entry: Manifest row from the latest backup.

    Returns:
        True when size and content still match the pre-write snapshot.
    """
    expected_hash = entry.original_sha256
    expected_size = entry.original_size
    if expected_hash is None:
        if entry.kind != _KIND_FULL:
            return False
        expected_hash = entry.sha256
        expected_size = entry.size
    if expected_size is not None and source.stat().st_size != expected_size:
        return False
    return sha256_file(source) == expected_hash


def _entry_covers_source(
    source: Path,
    relative: str,
    by_relative: dict[str, BackupFileEntry],
    backup_dir: Path,
) -> bool:
    """
    Return True when ``backup_dir`` already holds a matching snapshot of ``source``.

    Args:
        source: Live file on the mount.
        relative: Path relative to the mount root.
        by_relative: Manifest entries keyed by ``relative_path``.
        backup_dir: Directory of the candidate backup.

    Returns:
        True when the artifact exists and the live file has not changed.
    """
    entry = by_relative.get(relative)
    if entry is None:
        return False
    if not resolve_artifact(backup_dir, entry).is_file():
        return False
    return _source_matches_entry(source, entry)


def _reusable_backup(
    root: Path,
    sources: list[tuple[Path, str]],
    on_progress: BackupProgressCallback | None,
) -> BackupResult | None:
    """
    Return the latest backup when it already covers every source file.

    Args:
        root: Host backup parent for one volume.
        sources: Files this run would copy, as ``(path, relative)``.
        on_progress: Optional bar callback; fired only when reuse succeeds.

    Returns:
        The existing ``BackupResult``, or None when a new copy is required.
    """
    latest = _latest_backup_dir(root)
    if latest is None:
        return None
    try:
        manifest = BackupManifest.load(latest)
    except (OSError, ValueError, KeyError):
        return None
    by_relative = {entry.relative_path: entry for entry in manifest.files}
    if any(
        not _entry_covers_source(source, relative, by_relative, latest)
        for source, relative in sources
    ):
        return None
    if on_progress is not None:
        total = sum(source.stat().st_size for source, _ in sources) or len(sources)
        on_progress(0, total)
        on_progress(total, total)
    logger.info(
        "backup_reused",
        backup_id=manifest.backup_id,
        backup_dir=str(latest),
        file_count=len(sources),
    )
    return BackupResult(backup_id=manifest.backup_id, backup_dir=latest, manifest=manifest)


def _previous_snapshot(
    root: Path,
) -> tuple[Path, dict[str, BackupFileEntry]] | None:
    """
    Load the latest snapshot's entries, if one exists.

    Args:
        root: Volume backup parent.

    Returns:
        Snapshot directory and entries keyed by relative path, or None.
    """
    latest = _latest_backup_dir(root)
    if latest is None:
        return None
    try:
        manifest = BackupManifest.load(latest)
    except (OSError, ValueError, KeyError):
        return None
    return latest, {entry.relative_path: entry for entry in manifest.files}


def _promote_legacy_entry(
    artifact: Path, previous: BackupFileEntry, backup_dir: Path
) -> BackupFileEntry:
    """
    Copy a pre-CAS artifact into ``objects/`` and retarget the entry.

    Args:
        artifact: File inside an older snapshot directory.
        previous: Manifest row that still points at that in-snapshot path.
        backup_dir: Snapshot being written (its parent holds ``objects/``).

    Returns:
        The same logical file, now stored as ``objects/<sha256>``.
    """
    objects = backup_dir.parent / _OBJECTS
    digest = previous.sha256
    destination = objects / digest
    if not destination.is_file():
        objects.mkdir(parents=True, exist_ok=True)
        atomic_copy_file(artifact, destination)
    return BackupFileEntry(
        relative_path=previous.relative_path,
        sha256=digest,
        size=previous.size,
        kind=previous.kind,
        stored_as=f"{_OBJECTS}/{digest}",
        original_sha256=previous.original_sha256,
        original_size=previous.original_size,
    )


def _entry_for_source(
    source: Path,
    relative: str,
    backup_dir: Path,
    previous: tuple[Path, dict[str, BackupFileEntry]] | None,
) -> BackupFileEntry:
    """
    Reuse a prior object when the live file is unchanged, otherwise store one.

    Args:
        source: File on the mount.
        relative: Path relative to the mount root.
        backup_dir: Snapshot directory being written.
        previous: Latest snapshot and its entries, if any.

    Returns:
        Manifest entry for this source.
    """
    if previous is not None:
        previous_dir, by_relative = previous
        prior = by_relative.get(relative)
        if prior is not None and _source_matches_entry(source, prior):
            artifact = resolve_artifact(previous_dir, prior)
            if artifact.is_file():
                stored = prior.stored_as or ""
                if stored.startswith(f"{_OBJECTS}/"):
                    return prior
                return _promote_legacy_entry(artifact, prior, backup_dir)
    return _store_backup_file(source, backup_dir, relative)


def _store_backup_file(source: Path, backup_dir: Path, relative: str) -> BackupFileEntry:
    """
    Store one source file as a content-addressed full copy or audio delta.

    Args:
        source: File on the mount.
        backup_dir: Timestamped snapshot directory.
        relative: Path relative to the mount root.

    Returns:
        Manifest entry describing the stored artifact.
    """
    objects = backup_dir.parent / _OBJECTS
    if is_audio_backup_path(source):
        data = source.read_bytes()
        try:
            payload = encode_audio_delta(data)
        except AudioDeltaError:
            payload = None
        if payload is not None:
            digest = _put_object(objects, payload)
            logger.info(
                "backup_delta",
                source=str(source),
                destination=str(objects / digest),
                original_size=len(data),
                delta_size=len(payload),
            )
            return BackupFileEntry(
                relative_path=relative,
                sha256=digest,
                size=len(payload),
                kind=_KIND_DELTA,
                stored_as=f"{_OBJECTS}/{digest}",
                original_sha256=hashlib.sha256(data).hexdigest(),
                original_size=len(data),
            )
    digest = _put_object_file(objects, source)
    logger.info("backup_copy", source=str(source), destination=str(objects / digest))
    size = source.stat().st_size
    return BackupFileEntry(
        relative_path=relative,
        sha256=digest,
        size=size,
        kind=_KIND_FULL,
        stored_as=f"{_OBJECTS}/{digest}",
        original_sha256=digest,
        original_size=size,
    )


def create_backup(
    *,
    source_mount: Path,
    files: list[Path],
    backup_root: Path | None = None,
    backup_id: str | None = None,
    on_progress: BackupProgressCallback | None = None,
) -> BackupResult:
    """
    Snapshot the given files into a timestamped backup directory.

    Artifacts live once under ``objects/<sha256>``. A new snapshot writes
    only blobs that are not already stored. When ``backup_id`` is omitted
    and every file still matches the latest snapshot, that snapshot is
    reused and no new directory is created.

    Args:
        source_mount: Mount root; relative paths in manifest are from here.
        files: Absolute or mount-relative file paths to copy.
        backup_root: Parent directory for backups; defaults to a host
            directory from ``default_backup_root``, not the USB.
        backup_id: Optional directory name; defaults to UTC timestamp.
            An explicit id always writes a new directory.
        on_progress: Optional ``(bytes_done, bytes_total)`` callback. Fired
            at 0 and after each file so a bar can show backup ETA.

    Returns:
        BackupResult with backup_dir and manifest.

    Raises:
        FileNotFoundError: If a source file does not exist.
        ValueError: If no files are provided.
    """
    if not files:
        raise ValueError("At least one file must be specified for backup")

    mount = source_mount.resolve()
    created_at = datetime.now(UTC)
    root = (backup_root or default_backup_root(mount)).resolve()
    sources = _backup_sources(mount, files)
    if backup_id is None:
        reused = _reusable_backup(root, sources, on_progress)
        if reused is not None:
            _write_latest(root, reused.backup_id)
            return reused
    previous = _previous_snapshot(root)

    if backup_id is not None:
        backup_dir = root / backup_id
        backup_dir.mkdir(parents=True, exist_ok=False)
    else:
        # The id has one-second resolution, so two backups requested within
        # the same second (e.g. one operation gating straight into another)
        # would otherwise collide on mkdir. Suffix with a counter rather than
        # switching to a finer clock, so the common case keeps its plain,
        # readable timestamp.
        stem = created_at.strftime("%Y%m%dT%H%M%SZ")
        backup_id = stem
        suffix = 1
        while True:
            backup_dir = root / backup_id
            try:
                backup_dir.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                suffix += 1
                backup_id = f"{stem}-{suffix}"

    sizes = [source.stat().st_size for source, _ in sources]
    total_bytes = sum(sizes)
    use_bytes = total_bytes > 0
    total = total_bytes if use_bytes else len(sources)
    if on_progress is not None:
        on_progress(0, total)
    entries: list[BackupFileEntry] = []
    copied = 0
    for (source, relative), size in zip(sources, sizes, strict=True):
        entries.append(_entry_for_source(source, relative, backup_dir, previous))
        copied += size if use_bytes else 1
        if on_progress is not None:
            on_progress(copied, total)

    manifest = BackupManifest(
        backup_id=backup_id,
        created_at=created_at.isoformat(),
        source_mount=str(mount),
        files=tuple(entries),
    )
    manifest.write(backup_dir)
    _write_latest(root, backup_id)
    logger.info(
        "backup_completed",
        backup_id=backup_id,
        backup_dir=str(backup_dir),
        file_count=len(entries),
    )
    return BackupResult(backup_id=backup_id, backup_dir=backup_dir, manifest=manifest)
