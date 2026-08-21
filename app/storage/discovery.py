"""Read-only DJ library detection on mount paths."""

from dataclasses import dataclass
from pathlib import Path

import structlog

from app.core.domain import LibraryLocation, LibraryType

logger = structlog.get_logger(__name__)


def _path_ends_with(parts: tuple[str, ...], suffix: tuple[str, ...]) -> bool:
    """
    Return True if parts end with the suffix sequence (case-insensitive).

    Args:
        parts: Relative path components.
        suffix: Required trailing components.

    Returns:
        True when suffix matches the end of parts.
    """
    if len(suffix) > len(parts):
        return False
    tail = parts[-len(suffix) :]
    return tuple(p.lower() for p in tail) == tuple(s.lower() for s in suffix)


@dataclass(frozen=True)
class _DirMarker:
    """Matches when the current directory's path suffix equals ``parts``."""

    parts: tuple[str, ...]
    confidence: float
    label: str

    def locate(
        self, current: Path, rel_parts: tuple[str, ...], filenames: list[str]
    ) -> Path | None:
        """Return the directory itself when its trailing path components match."""
        del filenames
        return current if _path_ends_with(rel_parts, self.parts) else None


@dataclass(frozen=True)
class _FileMarker:
    """Matches when ``name`` is a file in the current directory."""

    name: str
    confidence: float
    label: str
    require_ancestor: str | None = None

    def locate(
        self, current: Path, rel_parts: tuple[str, ...], filenames: list[str]
    ) -> Path | None:
        """Return the matched file path, optionally gated on an ancestor directory."""
        if self.name not in filenames:
            return None
        if self.require_ancestor is not None and self.require_ancestor not in rel_parts:
            return None
        return current / self.name


@dataclass(frozen=True)
class _SuffixMarker:
    """Matches when any file carries ``suffix`` and an ancestor directory matches."""

    suffix: str
    confidence: float
    label: str
    require_ancestor: str

    def locate(
        self, current: Path, rel_parts: tuple[str, ...], filenames: list[str]
    ) -> Path | None:
        """Return the containing directory when a matching file is present."""
        if self.require_ancestor not in rel_parts:
            return None
        if not any(f.lower().endswith(self.suffix) for f in filenames):
            return None
        return current


Marker = _DirMarker | _FileMarker | _SuffixMarker

_REKORDBOX_MARKERS: tuple[Marker, ...] = (
    _DirMarker(("PIONEER", "rekordbox"), 0.95, "PIONEER/rekordbox directory"),
    _DirMarker(("rekordbox",), 0.70, "rekordbox directory"),
    _FileMarker("export.pdb", 0.85, "export.pdb file"),
    _FileMarker("master.db", 0.81, "master.db file"),
)

_SERATO_MARKERS: tuple[Marker, ...] = (
    _DirMarker(("_Serato_",), 0.95, "_Serato_ directory"),
    _DirMarker(("Serato",), 0.75, "Serato directory"),
    _FileMarker("database V2", 0.90, "Serato/database V2", require_ancestor="Serato"),
    _FileMarker("database V2", 0.85, "database V2 file"),
    _SuffixMarker(".crate", 0.60, "Serato .crate file", require_ancestor="Subcrates"),
)


class LibraryDiscovery:
    """Walk mount trees and detect Rekordbox or Serato libraries (read-only)."""

    def __init__(self, max_depth: int = 8, max_nodes: int = 25_000) -> None:
        """
        Initialize discovery with a maximum walk depth.

        Args:
            max_depth: Maximum directory depth below mount root to search.
            max_nodes: Maximum directories to visit before stopping (safety cap).
        """
        self._max_depth = max_depth
        self._max_nodes = max_nodes
        self._nodes_visited = 0

    def detect_on_mount(self, mount_path: Path) -> list[LibraryLocation]:
        """
        Detect all DJ libraries under a single mount.

        Args:
            mount_path: Root path to scan (e.g. /mnt/usb).

        Returns:
            Deduplicated list of LibraryLocation sorted by confidence descending.
        """
        if not mount_path.exists():
            logger.warning("mount_missing", path=str(mount_path))
            return []

        found: dict[str, LibraryLocation] = {}
        mount_resolved = mount_path.resolve()
        self._nodes_visited = 0

        for dirpath, dirnames, filenames in self._walk_limited(mount_resolved):
            if self._nodes_visited >= self._max_nodes:
                logger.warning(
                    "walk_limit_reached",
                    mount=str(mount_resolved),
                    max_nodes=self._max_nodes,
                )
                break
            current = Path(dirpath)
            depth = len(current.relative_to(mount_resolved).parts)
            rel_parts = current.relative_to(mount_resolved).parts if depth > 0 else ()

            for markers, library_type in (
                (_REKORDBOX_MARKERS, LibraryType.REKORDBOX),
                (_SERATO_MARKERS, LibraryType.SERATO),
            ):
                self._apply_markers(
                    markers, library_type, current, rel_parts, filenames, mount_resolved, found
                )

            # Prune hidden dirs to reduce noise
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        results = sorted(found.values(), key=lambda loc: (-loc.confidence, str(loc.path)))
        logger.info(
            "mount_scan_complete",
            mount=str(mount_resolved),
            libraries_found=len(results),
        )
        return results

    def _walk_limited(self, root: Path):
        """
        Yield os.walk-style tuples respecting max_depth.

        Args:
            root: Mount root path.

        Yields:
            (dirpath, dirnames, filenames) tuples.
        """
        root_str = str(root)
        for dirpath, dirnames, filenames in _os_walk(root_str):
            current = Path(dirpath)
            try:
                depth = len(current.relative_to(root).parts)
            except ValueError:
                depth = 0
            if depth > self._max_depth:
                dirnames.clear()
                continue
            self._nodes_visited += 1
            yield dirpath, dirnames, filenames

    def _apply_markers(
        self,
        markers: tuple[Marker, ...],
        library_type: LibraryType,
        current: Path,
        rel_parts: tuple[str, ...],
        filenames: list[str],
        mount: Path,
        found: dict[str, LibraryLocation],
    ) -> None:
        """
        Record every marker that matches at the current directory.

        Args:
            markers: Vendor marker set to evaluate.
            library_type: Vendor the markers belong to.
            current: Directory being visited.
            rel_parts: Path components of ``current`` relative to the mount root.
            filenames: Filenames directly inside ``current``.
            mount: Mount root.
            found: Mutable detection map keyed by resolved path.
        """
        for marker in markers:
            path = marker.locate(current, rel_parts, filenames)
            if path is not None:
                self._add(found, path, library_type, marker.confidence, mount, (marker.label,))

    @staticmethod
    def _add(
        found: dict[str, LibraryLocation],
        path: Path,
        library_type: LibraryType,
        confidence: float,
        mount: Path,
        indicators: tuple[str, ...],
    ) -> None:
        """
        Insert or upgrade a detection entry keyed by resolved path.

        Args:
            found: Mutable detection map.
            path: Detected library path.
            library_type: Vendor type.
            confidence: Heuristic score.
            mount: Mount root.
            indicators: Detection reason strings.
        """
        key = str(path.resolve())
        existing = found.get(key)
        if existing is None or confidence > existing.confidence:
            found[key] = LibraryLocation(
                path=path.resolve(),
                library_type=library_type,
                confidence=round(confidence, 2),
                mount_path=mount,
                indicators=indicators,
            )
            logger.debug(
                "library_candidate",
                path=key,
                library_type=library_type.value,
                confidence=confidence,
                indicators=indicators,
            )


def _os_walk(top: str):
    """Import os.walk lazily for test patching."""
    import os

    yield from os.walk(top, topdown=True, followlinks=False)
