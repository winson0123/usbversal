"""CLI argument parsing and command dispatch."""

import argparse
import json
import sys

import structlog

from app.adapters.base import (
    DatabaseNotFoundError,
    SeratoLibraryNotFoundError,
    UnsupportedDatabaseError,
)
from app.adapters.serato.writer import CrateExistsError
from app.core.apply_plan import ApplyPlanError
from app.services.apply_service import apply_plan_file
from app.services.backup_service import backup_mount_libraries, backup_result_to_dict
from app.services.crate_service import list_serato_crates
from app.services.migration_service import (
    MigrationError,
    PlaylistNotFoundError,
    SeratoLibraryRequiredError,
    migrate_playlist_to_crate,
)
from app.services.playlist_service import list_rekordbox_playlists
from app.services.rollback_service import rollback_mount_libraries, rollback_result_to_dict
from app.services.scan_service import run_scan
from app.storage.rollback import (
    BackupNotFoundError,
    BackupVerificationError,
    MountMismatchError,
)

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
        description="Usbversal DJ database CLI",
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

    backup_parser = sub.add_parser(
        "backup",
        help="Copy Rekordbox library files to a timestamped backup (read-only)",
    )
    backup_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /mnt/usb)",
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
        help="Mount path (e.g. /mnt/usb)",
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

    crates_parser = sub.add_parser(
        "list-crates",
        help="List Serato crates on a mount (read-only)",
    )
    crates_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /mnt/usb)",
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
        help="Mount path (e.g. /mnt/usb)",
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

    apply_parser = sub.add_parser(
        "apply",
        help="Run operations from a JSON plan file (backup-gated writes)",
    )
    apply_parser.add_argument(
        "--mount",
        required=True,
        help="Mount path (e.g. /mnt/usb)",
    )
    apply_parser.add_argument(
        "--plan",
        required=True,
        help="Path to apply plan JSON file",
    )
    apply_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate plan and show outcomes without backup or writes",
    )
    apply_parser.add_argument(
        "--target",
        default=None,
        help="Backup parent directory (default: <mount>/backups)",
    )
    apply_parser.add_argument(
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
    except (FileNotFoundError, ValueError) as exc:
        log.error("backup_failed", error=str(exc))
        return 1
    except OSError as exc:
        log.error("backup_failed", error=str(exc))
        return 1

    if args.json:
        print(json.dumps(backup_result_to_dict(result), indent=2))
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
    except (BackupNotFoundError, BackupVerificationError, MountMismatchError) as exc:
        log.error("rollback_failed", error=str(exc))
        return 1
    except (FileNotFoundError, ValueError, OSError) as exc:
        log.error("rollback_failed", error=str(exc))
        return 1

    if args.json:
        print(json.dumps(rollback_result_to_dict(result), indent=2))
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
            args.mount,
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
    ) as exc:
        log.error("migrate_playlist_failed", error=str(exc))
        return 1
    except (DatabaseNotFoundError, UnsupportedDatabaseError, ValueError, OSError) as exc:
        log.error("migrate_playlist_failed", error=str(exc))
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
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
        if len(plan.skipped_paths) > 10:
            print(f"  ... and {len(plan.skipped_paths) - 10} more")
    if result.dry_run:
        print("\n(dry-run: no backup or write performed)")
        return 0

    print(f"\nBackup ID: {result.backup.backup_id}")
    print(f"Backup dir: {result.backup.backup_dir}")
    print(f"Wrote crate: {result.crate_path}")
    return 0


def _cmd_apply(args: argparse.Namespace) -> int:
    """
    Run apply: execute operations from a JSON plan file.

    Args:
        args: Parsed namespace with mount, plan path, and flags.

    Returns:
        Exit code 0 on success, 1 on failure.
    """
    log = structlog.get_logger()
    try:
        result = apply_plan_file(
            args.mount,
            args.plan,
            dry_run=args.dry_run,
            backup_root=args.target,
        )
    except ApplyPlanError as exc:
        log.error("apply_failed", error=str(exc))
        return 1
    except (
        PlaylistNotFoundError,
        SeratoLibraryRequiredError,
        CrateExistsError,
        MigrationError,
    ) as exc:
        log.error("apply_failed", error=str(exc))
        return 1
    except (ValueError, OSError) as exc:
        log.error("apply_failed", error=str(exc))
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    print(f"Plan: {result.plan_path}")
    print(f"Mount: {result.mount}")
    print(f"Operations: {len(result.operations)} ({result.success_count} ok)")
    if result.dry_run:
        print("\n(dry-run: no backup or writes)")
    for op in result.operations:
        if op.result is None:
            print(f"  [{op.index}] {op.op}: failed — {op.error}")
            continue
        migration = op.result
        print(
            f"  [{op.index}] {op.op}: {migration.get('playlist_name')} "
            f"→ Subcrates/{migration.get('crate_name')}.crate "
            f"({migration.get('serato_track_count')} tracks, "
            f"{migration.get('skipped_count')} skipped)",
        )
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
    except SeratoLibraryNotFoundError as exc:
        log.error("list_crates_failed", error=str(exc))
        return 1
    except OSError as exc:
        log.error("list_crates_failed", error=str(exc))
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
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

    if args.command == "scan":
        return _cmd_scan(args)
    if args.command == "list-playlists":
        return _cmd_list_playlists(args)
    if args.command == "backup":
        return _cmd_backup(args)
    if args.command == "rollback":
        return _cmd_rollback(args)
    if args.command == "list-crates":
        return _cmd_list_crates(args)
    if args.command == "migrate-playlist":
        return _cmd_migrate_playlist(args)
    if args.command == "apply":
        return _cmd_apply(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
