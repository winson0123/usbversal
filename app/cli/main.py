"""CLI argument parsing and command dispatch."""

import argparse
import json
import sys

import structlog

from app.adapters.base import DatabaseNotFoundError, UnsupportedDatabaseError
from app.services.playlist_service import list_rekordbox_playlists
from app.services.scan_service import run_scan

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
)


def _build_parser() -> argparse.ArgumentParser:
    """
    Build the top-level argument parser.

    Returns:
        Configured ArgumentParser with subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="usbversal",
        description="Usbversal DJ database CLI (read-only)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="Scan mounts and detect DJ libraries")
    scan_parser.add_argument(
        "--mount",
        help="Scan only this mount path (e.g. /mnt/usb)",
        default=None,
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    list_parser = sub.add_parser(
        "list-playlists",
        help="List Rekordbox playlists on a mount (read-only)",
    )
    list_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /mnt/usb)",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    return parser


def _cmd_scan(args: argparse.Namespace) -> int:
    """
    Run the scan command and print results.

    Args:
        args: Parsed namespace with mount and json flags.

    Returns:
        Exit code 0 on success, 1 on failure.
    """
    try:
        result = run_scan(mount=args.mount)
    except OSError as exc:
        structlog.get_logger().error("scan_failed", error=str(exc))
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    print(f"Scanned {len(result.mounts)} mount(s), found {len(result.libraries)} library(ies)\n")
    for mp in result.mounts:
        print(f"  Mount: {mp.path} ({mp.source})")
    for lib in result.libraries:
        indicators = ", ".join(lib.indicators)
        print(
            f"  [{lib.library_type.value}] {lib.path} "
            f"(confidence={lib.confidence:.2f}) — {indicators}"
        )
    if not result.libraries:
        print("  (no libraries detected)")
    return 0


def _cmd_list_playlists(args: argparse.Namespace) -> int:
    """
    Run the list-playlists command.

    Args:
        args: Parsed namespace with mount and json flags.

    Returns:
        Exit code 0 on success, 1 on user/adapter error, 2 on unsupported format.
    """
    log = structlog.get_logger()
    try:
        result = list_rekordbox_playlists(args.mount)
    except DatabaseNotFoundError as exc:
        log.error("list_playlists_failed", error=str(exc))
        return 1
    except UnsupportedDatabaseError as exc:
        log.error("list_playlists_unsupported", error=str(exc))
        return 2
    except OSError as exc:
        log.error("list_playlists_failed", error=str(exc))
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    lib = result.library
    print(f"Database: {lib.database_path} ({lib.db_format.value})")
    print(f"Playlists: {len(result.playlists)}\n")
    for pl in sorted(result.playlists, key=lambda p: (p.parent_id or 0, p.name)):
        kind = "folder" if pl.is_folder else "playlist"
        parent = f" parent={pl.parent_id}" if pl.parent_id is not None else ""
        tracks = f" tracks={pl.track_count}" if pl.track_count is not None else ""
        print(f"  [{kind}] {pl.id}: {pl.name}{parent}{tracks}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """
    CLI entrypoint.

    Args:
        argv: Optional argument list; uses sys.argv when None.

    Returns:
        Process exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return _cmd_scan(args)
    if args.command == "list-playlists":
        return _cmd_list_playlists(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
