# Backup Strategy

**Status:** design placeholder — not implemented.

## Principle

**No database write without a verified backup.**

## Backup Layout (Planned)

```text
<mount or cwd>/backups/<iso-timestamp>/
  manifest.json          # paths, checksums, job_id
  rekordbox/export.pdb   # mirrored relative paths
  serato/...             # all touched Serato DB files
```

## Procedure

1. Resolve all file paths the operation will touch
2. Create timestamped backup directory
3. Copy files atomically (copy to temp, fsync, rename)
4. Compute checksums (SHA-256)
5. Write `manifest.json`
6. Pass `backup_path` into `WriteContext`
7. Proceed with adapter write only after steps 1–6 succeed

## manifest.json (Planned)

| Field | Purpose |
|-------|---------|
| `backup_id` | Unique id for rollback CLI |
| `created_at` | ISO timestamp |
| `source_mount` | Original mount path |
| `files` | List of `{relative_path, sha256, size}` |

## Integrity

- Rekordbox: run `PRAGMA integrity_check` on backup copy before write
- Serato: verify file size/hash matches source after copy

## Related

- [rollback-flow.md](rollback-flow.md)
- [../adapters/rekordbox.md](../adapters/rekordbox.md)
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
