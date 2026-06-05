# CLI Flow

**Status:** implemented (scan, backup, rollback, migrate-playlist, apply).

## Thin CLI Principle

Every command follows:

```text
parse_args → validate_paths → build_context → dispatch_job_or_service → format_output → exit_code
```

No SQL, no Serato parsing, no backup file copying in CLI modules.

## Planned Commands

| Command | Job? | Primary delegate |
|---------|------|------------------|
| `scan` | yes | `storage` + `adapters.detect` |
| `list-playlists` | optional | `rekordbox` adapter |
| `list-crates` | optional | `serato` adapter |
| `backup` | yes | `storage.backup` |
| `apply` | no | `apply_service.apply_plan_file` |
| `rollback` | yes | `storage.rollback` |
| `jobs list/resume/cancel` | no | `jobs` registry |

## Exit Codes (Planned)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | User error (bad args, missing mount) |
| 2 | Operational failure (backup failed, DB locked) |
| 3 | Internal/unexpected error |

## Global Flags (Planned)

| Flag | Purpose |
|------|---------|
| `--mount` | USB root (e.g. `/mnt/usb`) |
| `--json` | Machine-readable output |
| `--verbose` | Debug logging |
| `--dry-run` | Validate plan without write |

## Example Flow: `scan`

```text
usbversal scan --mount /mnt/usb
  → validate mount exists
  → JobRunner.start(ScanJob(mount=/mnt/usb))
  → emit scan.mount_scanned, scan.library_found events
  → CLI prints summary table or JSON
```

## Related

- [../../CONTRIBUTING.md](../../CONTRIBUTING.md) — CLI thin-layer requirement
- [../workflows/agent-task-workflow.md](../workflows/agent-task-workflow.md)
