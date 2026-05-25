# Rollback Flow

**Status:** implemented (manual CLI rollback; automatic job rollback deferred).

## When Rollback Runs

| Trigger | Action |
|---------|--------|
| Adapter write failure | Automatic rollback from job |
| User `usbversal rollback` | Manual restore |
| Cancel during write step | Rollback if backup exists |

## Procedure

1. Load `manifest.json` for `backup_id`
2. Verify backup files exist and checksums match manifest
3. Optionally backup **current** (corrupted) files to `backups/pre-rollback-<ts>/`
4. Restore each file from backup copy to original path
5. Verify integrity (Rekordbox adapter)
6. Emit `storage.rollback_done`

## CLI

```bash
python -m app.cli rollback --mount /mnt/usb --backup-id <id>
python -m app.cli rollback --mount /mnt/usb --backup-id <id> --no-pre-rollback
```

## Safety

- Refuse rollback if manifest missing or checksum mismatch
- Never delete backup directory on rollback (retain for audit)

## Related

- [backup-strategy.md](backup-strategy.md)
- [../jobs/cancellation.md](../jobs/cancellation.md)
