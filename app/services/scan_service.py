"""Scan orchestration: mounts, discovery, events, and structured output."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import structlog

from app.core.domain import LibraryLocation, MountPoint
from app.core.events import LibraryDetected, LibraryScanCompleted, LibraryScanStarted
from app.storage.discovery import LibraryDiscovery
from app.storage.mounts import get_mount_scanner, resolve_mount_path

logger = structlog.get_logger(__name__)

EventEmitter = Callable[[Any], None]


@dataclass(frozen=True)
class ScanResult:
    """
    Outcome of a library scan operation.

    Attributes:
        mounts: Mount points that were scanned.
        libraries: Detected library locations.
        events: Serialized event payloads emitted during the scan.
    """

    mounts: tuple[MountPoint, ...]
    libraries: tuple[LibraryLocation, ...]
    events: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        """
        Convert scan result to a JSON-serializable dictionary.

        Returns:
            Dict with mounts, libraries, and event_count.
        """
        return {
            "mounts": [{"path": str(m.path), "source": m.source} for m in self.mounts],
            "libraries": [
                {
                    "path": str(lib.path),
                    "type": lib.library_type.value,
                    "confidence": lib.confidence,
                    "mount_path": str(lib.mount_path),
                    "indicators": list(lib.indicators),
                }
                for lib in self.libraries
            ],
            "event_count": len(self.events),
        }


def _default_emitter(event: Any) -> None:
    """
    Log structured events via structlog.

    Args:
        event: Event dataclass with to_dict().
    """
    payload = event.to_dict()
    event_type = type(event).__name__
    logger.info("event", event_type=event_type, **payload)


def run_scan(
    *,
    mount: str | None = None,
    emit: EventEmitter | None = None,
) -> ScanResult:
    """
    Scan mount points and detect DJ libraries (read-only).

    Args:
        mount: Optional single mount path (e.g. /mnt/usb). When set, only this
            mount is scanned; otherwise all platform mounts are enumerated.
        emit: Optional callback for each event; defaults to structlog logging.

    Returns:
        ScanResult containing mounts, libraries, and emitted event payloads.
    """
    emitter = emit or _default_emitter
    discovery = LibraryDiscovery()
    events: list[dict[str, Any]] = []

    def record(event: Any) -> None:
        events.append(event.to_dict())
        emitter(event)

    if mount:
        mount_path = resolve_mount_path(mount)
        mounts = [MountPoint(path=mount_path, source="user_specified")]
    else:
        mounts = get_mount_scanner().list_mounts()

    mount_paths = tuple(str(m.path) for m in mounts)
    started = LibraryScanStarted(mounts=mount_paths)
    record(started)

    logger.info("scan_started", mount_count=len(mounts), mounts=mount_paths)

    all_libraries: list[LibraryLocation] = []
    for mp in mounts:
        logger.info("scanning_mount", path=str(mp.path), source=mp.source)
        libraries = discovery.detect_on_mount(mp.path)
        all_libraries.extend(libraries)
        for lib in libraries:
            detected = LibraryDetected(
                path=str(lib.path),
                library_type=lib.library_type.value,
                confidence=lib.confidence,
                mount_path=str(lib.mount_path),
                indicators=lib.indicators,
            )
            record(detected)

    completed = LibraryScanCompleted(
        mount_count=len(mounts),
        library_count=len(all_libraries),
    )
    record(completed)

    logger.info(
        "scan_completed",
        mount_count=len(mounts),
        library_count=len(all_libraries),
    )

    return ScanResult(
        mounts=tuple(mounts),
        libraries=tuple(all_libraries),
        events=tuple(events),
    )
