"""Read-only DJ library detection on mount paths."""

from pathlib import Path

import structlog

from app.core.domain import LibraryLocation, LibraryType

logger = structlog.get_logger(__name__)

# (relative path parts OR filename, confidence, indicator label)
_REKORDBOX_MARKERS: tuple[tuple[tuple[str, ...] | str, float, str], ...] = (
    (("PIONEER", "rekordbox"), 0.95, "PIONEER/rekordbox directory"),
    (("export.pdb",), 0.9, "export.pdb file"),
    (("master.db",), 0.85, "master.db file"),
    (("rekordbox",), 0.7, "rekordbox directory"),
)

_SERATO_MARKERS: tuple[tuple[tuple[str, ...] | str, float, str], ...] = (
    (("_Serato_",), 0.95, "_Serato_ directory"),
    (("Serato", "database V2"), 0.9, "Serato/database V2"),
    (("Serato",), 0.75, "Serato directory"),
    (("database V2",), 0.85, "database V2 file"),
    ((".crate",), 0.6, "Serato .crate file"),
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

            self._check_rekordbox(current, rel_parts, filenames, mount_resolved, found)
            self._check_serato(current, rel_parts, filenames, mount_resolved, found)

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

    def _check_rekordbox(
        self,
        current: Path,
        rel_parts: tuple[str, ...],
        filenames: list[str],
        mount: Path,
        found: dict[str, LibraryLocation],
    ) -> None:
        """Apply Rekordbox heuristics at the current path."""
        for marker, confidence, label in _REKORDBOX_MARKERS:
            if isinstance(marker, str):
                if marker in filenames:
                    loc_path = current / marker
                    self._add(found, loc_path, LibraryType.REKORDBOX, confidence, mount, (label,))
                continue

            if self._path_ends_with(rel_parts, marker):
                loc_path = current
                self._add(found, loc_path, LibraryType.REKORDBOX, confidence, mount, (label,))

            # Also check if marker is a direct child
            if len(marker) == 1 and marker[0] in filenames:
                loc_path = current / marker[0]
                self._add(
                    found,
                    loc_path,
                    LibraryType.REKORDBOX,
                    confidence * 0.95,
                    mount,
                    (label,),
                )

    def _check_serato(
        self,
        current: Path,
        rel_parts: tuple[str, ...],
        filenames: list[str],
        mount: Path,
        found: dict[str, LibraryLocation],
    ) -> None:
        """Apply Serato heuristics at the current path."""
        for marker, confidence, label in _SERATO_MARKERS:
            if marker == (".crate",):
                crate_files = [f for f in filenames if f.lower().endswith(".crate")]
                if crate_files and "Subcrates" in rel_parts:
                    loc_path = current
                    self._add(found, loc_path, LibraryType.SERATO, confidence, mount, (label,))
                continue

            if isinstance(marker, str):
                if marker in filenames:
                    loc_path = current / marker
                    self._add(found, loc_path, LibraryType.SERATO, confidence, mount, (label,))
                continue

            if self._path_ends_with(rel_parts, marker):
                loc_path = current
                self._add(found, loc_path, LibraryType.SERATO, confidence, mount, (label,))

            if len(marker) == 2:
                parent_name = marker[0]
                child_name = marker[1]
                if parent_name in rel_parts and child_name in filenames:
                    loc_path = current / child_name if current.name != child_name else current
                    self._add(found, loc_path, LibraryType.SERATO, confidence, mount, (label,))

    @staticmethod
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
