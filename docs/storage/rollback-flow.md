# Rollback Flow

**Status:** implemented (storage API; automatic job rollback deferred).

## When Rollback Runs

| Trigger | Action |
|---------|--------|
| Adapter write failure | Automatic rollback from job |
| Caller asks storage to restore | Manual restore |
| Cancel during write step | Rollback if backup exists |

## Procedure

1. Load `manifest.json` for `backup_id`
2. Verify backup files exist and checksums match manifest
3. Optionally backup **current** (corrupted) files to `backups/pre-rollback-<ts>/`
4. Restore each file from backup copy to original path
5. Verify integrity (Rekordbox adapter)
6. Emit `storage.rollback_done`

Rollback is invoked from services after a failed write. There is no operator
command for it.

## Safety

- Refuse rollback if manifest missing or checksum mismatch
- Never delete backup directory on rollback (retain for audit)

## Related

- [backup-strategy.md](backup-strategy.md)
- [../jobs/cancellation.md](../jobs/cancellation.md)
