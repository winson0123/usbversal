"""CLI argument parsing and command dispatch."""

import argparse
import json
import sys

import structlog

from app.services.backup_service import backup_mount_libraries, backup_result_to_dict
from app.services.crate_service import list_serato_crates
from app.services.errors import (
    BackupNotFoundError,
    BackupVerificationError,
    CrateExistsError,
    DatabaseNotFoundError,
    MigrationError,
    MountMismatchError,
    PlaylistNotFoundError,
    SeratoLibraryNotFoundError,
    SeratoLibraryRequiredError,
    UnsupportedDatabaseError,
)
from app.services.library import open_library, probe_mount
from app.services.migration_service import migrate_playlist_to_crate
from app.services.playlist_service import list_rekordbox_playlists
from app.services.rollback_service import rollback_mount_libraries, rollback_result_to_dict
from app.services.sync_service import playlist_sync_states, sync_states_to_dict
from app.tui.app import run as run_tui

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)


def _build_parser() -> argparse.ArgumentParser:
    """
    Build the top-level argument parser.

    Returns:
        Configured ArgumentParser with subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="usbversal",
        description="Usbversal DJ database CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser(
        "list-playlists",
        help="List Rekordbox playlists on a mount (read-only)",
    )
    list_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /media/$USER/MY_USB)",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    backup_parser = sub.add_parser(
        "backup",
        help="Copy Rekordbox library files to a timestamped backup (read-only)",
    )
    backup_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /media/$USER/MY_USB)",
    )
    backup_parser.add_argument(
        "--target",
        default=None,
        help="Backup parent directory (default: <mount>/backups)",
    )
    backup_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    rollback_parser = sub.add_parser(
        "rollback",
        help="Restore library files from a prior backup manifest",
    )
    rollback_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /media/$USER/MY_USB)",
    )
    rollback_parser.add_argument(
        "--backup-id",
        required=True,
        help="Backup directory name under backups/ (e.g. 20260525T075946Z)",
    )
    rollback_parser.add_argument(
        "--target",
        default=None,
        help="Backup parent directory (default: <mount>/backups)",
    )
    rollback_parser.add_argument(
        "--no-pre-rollback",
        action="store_true",
        help="Skip safety backup of current files before restore",
    )
    rollback_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    probe_parser = sub.add_parser(
        "probe",
        help="Report what DJ library sits on a mount (stat-only)",
    )
    probe_parser.add_argument(
        "--mount", required=True, help="Mount path (e.g. /media/$USER/MY_USB)"
    )
    probe_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    status_parser = sub.add_parser(
        "status",
        help="Show per-playlist sync state (red/yellow/green)",
    )
    status_parser.add_argument(
        "--mount", required=True, help="Mount path (e.g. /media/$USER/MY_USB)"
    )
    status_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    crates_parser = sub.add_parser(
        "list-crates",
        help="List Serato crates on a mount (read-only)",
    )
    crates_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /media/$USER/MY_USB)",
    )
    crates_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    migrate_parser = sub.add_parser(
        "migrate-playlist",
        help="Copy a Rekordbox playlist to a new Serato crate (backup-gated)",
    )
    migrate_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /media/$USER/MY_USB)",
    )
    migrate_group = migrate_parser.add_mutually_exclusive_group(required=True)
    migrate_group.add_argument(
        "--playlist-id",
        type=int,
        help="Rekordbox playlist id",
    )
    migrate_group.add_argument(
        "--playlist-name",
        help="Rekordbox playlist name (exact match)",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show mapping only; do not backup or write",
    )
    migrate_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing Subcrates/<name>.crate",
    )
    migrate_parser.add_argument(
        "--target",
        default=None,
        help="Backup parent directory (default: <mount>/backups)",
    )
    migrate_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    sub.add_parser(
        "tui",
        help="Launch the interactive terminal UI",
    )

    return parser


def _cmd_tui(_args: argparse.Namespace) -> int:
    """
    Launch the interactive TUI.

    Args:
        _args: Parsed namespace; the ``tui`` subcommand takes no options.

    Returns:
        0 once the TUI exits.
    """
    run_tui()
    return 0


def _emit_json(payload: object) -> None:
    """Print ``payload`` as indented JSON on stdout."""
    print(json.dumps(payload, indent=2))


def _cmd_probe(args: argparse.Namespace) -> int:
    """
    Report what DJ library sits on a mount.

    Args:
        args: Parsed namespace with mount and json flags.

    Returns:
        Exit code 0 when a supported library is present, 1 otherwise.
    """
    probe = probe_mount(args.mount)
    if probe is None:
        if args.json:
            _emit_json({"mount": args.mount, "is_dj_usb": False, "reason": "empty"})
        else:
            print(f"No stick at {args.mount} (path absent or empty)")
        return 1
    if args.json:
        _emit_json(probe.to_dict())
        return 0 if probe.is_dj_usb and probe.is_supported else 1
    if not probe.is_dj_usb:
        print(f"Not a DJ USB: {probe.mount}")
        return 1
    print(f"Mount: {probe.mount}")
    print(f"Rekordbox: {probe.rekordbox_database} ({probe.rekordbox_format.value})")
    print(f"Serato: {probe.serato_database or '(none — needs bootstrapping)'}")
    if not probe.is_supported:
        print("Unsupported Rekordbox format")
        return 1
    return 0


_STATE_LABEL = {"not_synced": "not synced", "partial": "partial", "synced": "synced"}


def _cmd_status(args: argparse.Namespace) -> int:
    """
    Show how much of each playlist has reached Serato.

    Args:
        args: Parsed namespace with mount and json flags.

    Returns:
        Exit code 0 on success, 1 on failure.
    """
    log = structlog.get_logger()
    try:
        states = playlist_sync_states(open_library(args.mount))
    except (SeratoLibraryNotFoundError, ValueError, OSError) as exc:
        log.error("status_failed", error=str(exc))
        return 1

    if args.json:
        _emit_json(sync_states_to_dict(states))
        return 0
    for state in states:
        blocked = f"  [{state.blocked} not in Serato library]" if state.blocked else ""
        print(
            f"  {_STATE_LABEL[state.state.value]:<11} "
            f"{state.in_crate:>4}/{state.total:<4} {state.playlist_name}{blocked}"
        )
    summary = sync_states_to_dict(states)["summary"]
    print(
        f"\n{len(states)} playlists: "
        + ", ".join(f"{v} {_STATE_LABEL[k]}" for k, v in summary.items())
    )
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
        result = list_rekordbox_playlists(open_library(args.mount))
    except UnsupportedDatabaseError as exc:
        log.error("list_playlists_unsupported", error=str(exc))
        return 2
    except (DatabaseNotFoundError, OSError) as exc:
        log.error("list_playlists_failed", error=str(exc))
        return 1

    if args.json:
        _emit_json(result.to_dict())
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


def _cmd_backup(args: argparse.Namespace) -> int:
    """
    Run the backup command.

    Args:
        args: Parsed namespace with mount, target, and json flags.

    Returns:
        Exit code 0 on success, 1 on failure.
    """
    log = structlog.get_logger()
    try:
        result = backup_mount_libraries(args.mount, backup_root=args.target)
    except (FileNotFoundError, ValueError, OSError) as exc:
        log.error("backup_failed", error=str(exc))
        return 1

    if args.json:
        _emit_json(backup_result_to_dict(result))
        return 0
    print(f"Backup ID: {result.backup_id}")
    print(f"Directory: {result.backup_dir}")
    print(f"Manifest: {result.backup_dir / 'manifest.json'}")
    print(f"Files: {len(result.manifest.files)}")
    for entry in result.manifest.files:
        print(f"  {entry.relative_path} ({entry.size} bytes, sha256={entry.sha256[:12]}...)")
    return 0


def _cmd_rollback(args: argparse.Namespace) -> int:
    """
    Run the rollback command.

    Args:
        args: Parsed namespace with mount, backup_id, target, and json flags.

    Returns:
        Exit code 0 on success, 1 on failure.
    """
    log = structlog.get_logger()
    try:
        result = rollback_mount_libraries(
            args.mount,
            args.backup_id,
            backup_root=args.target,
            pre_rollback=not args.no_pre_rollback,
        )
    except (
        BackupNotFoundError,
        BackupVerificationError,
        MountMismatchError,
        FileNotFoundError,
        ValueError,
        OSError,
    ) as exc:
        log.error("rollback_failed", error=str(exc))
        return 1

    if args.json:
        _emit_json(rollback_result_to_dict(result))
        return 0
    print(f"Restored from backup: {result.backup_id}")
    print(f"Backup directory: {result.backup_dir}")
    print(f"Files restored: {len(result.restored_paths)}")
    for relative in result.restored_paths:
        print(f"  {relative}")
    if result.pre_rollback_backup_dir:
        print(f"Pre-rollback safety copy: {result.pre_rollback_backup_dir}")
    return 0


def _cmd_migrate_playlist(args: argparse.Namespace) -> int:
    """
    Run migrate-playlist: Rekordbox playlist to Serato crate.

    Args:
        args: Parsed namespace with mount, playlist selector, and flags.

    Returns:
        Exit code 0 on success, 1 on failure.
    """
    log = structlog.get_logger()
    try:
        result = migrate_playlist_to_crate(
            open_library(args.mount),
            playlist_id=args.playlist_id,
            playlist_name=args.playlist_name,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            backup_root=args.target,
        )
    except (
        PlaylistNotFoundError,
        SeratoLibraryRequiredError,
        CrateExistsError,
        MigrationError,
        BackupVerificationError,
    ) as exc:
        log.error("migrate_playlist_failed", error=str(exc))
        return 1
    except (DatabaseNotFoundError, UnsupportedDatabaseError, ValueError, OSError) as exc:
        log.error("migrate_playlist_failed", error=str(exc))
        return 1

    if args.json:
        _emit_json(result.to_dict())
        return 0
    plan = result.plan
    print(f"Playlist: {plan.playlist_name} (id={plan.playlist_id})")
    print(f"Target crate: Subcrates/{plan.crate_name}.crate")
    print(
        f"Tracks: {len(plan.rekordbox_paths)} in Rekordbox, "
        f"{len(plan.serato_paths)} matched in Serato, "
        f"{len(plan.skipped_paths)} skipped",
    )
    if plan.skipped_paths:
        print("\nSkipped (not in Serato database V2):")
        for path in plan.skipped_paths[:10]:
            print(f"  {path}")
        leftover = len(plan.skipped_paths) - 10
        if leftover > 0:
            print(f"  ... and {leftover} more")
    if result.dry_run:
        print("\n(dry-run: no backup or write performed)")
        return 0
    print(f"\nBackup ID: {result.backup.backup_id}")
    print(f"Backup dir: {result.backup.backup_dir}")
    print(f"Wrote crate: {result.crate_path}")
    return 0


def _cmd_list_crates(args: argparse.Namespace) -> int:
    """
    Run the list-crates command.

    Args:
        args: Parsed namespace with mount and json flags.

    Returns:
        Exit code 0 on success, 1 on failure.
    """
    log = structlog.get_logger()
    try:
        result = list_serato_crates(args.mount)
    except (SeratoLibraryNotFoundError, OSError) as exc:
        log.error("list_crates_failed", error=str(exc))
        return 1

    if args.json:
        _emit_json(result.to_dict())
        return 0
    lib = result.library
    print(f"Serato: {lib.serato_root}")
    print(f"Database: {lib.database_path} ({lib.database_track_count} tracks indexed)")
    print(f"Crates: {len(result.crates)}\n")
    for crate in result.crates:
        print(f"  {crate.name}: {crate.track_count} tracks")
        print(f"    {crate.path}")
    if not result.crates:
        print("  (no .crate files under Subcrates/)")
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
    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


_COMMANDS = {
    "probe": _cmd_probe,
    "status": _cmd_status,
    "list-playlists": _cmd_list_playlists,
    "backup": _cmd_backup,
    "rollback": _cmd_rollback,
    "list-crates": _cmd_list_crates,
    "migrate-playlist": _cmd_migrate_playlist,
    "tui": _cmd_tui,
}


if __name__ == "__main__":
    sys.exit(main())
