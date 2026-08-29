# Backup Strategy

**Status:** implemented (host-side copies + audio tag deltas).

## Principle

**No database or audio-tag write without a verified backup.**

Backups live on the **host**, not the USB. Audio is stored as a binary
delta of the tag region (head/tail around the audio payload), not a second
copy of the song. Rekordbox and Serato database files are still copied
whole — they are small.

Default root:

| OS | Path |
|----|------|
| Linux / macOS | `~/.local/share/usbversal/backups/<volume>/` |
| Windows | `%LOCALAPPDATA%/usbversal/backups/<volume>/` |

Override with `USBVERSAL_BACKUP_ROOT`. Volume is the mount folder name
(`WONSIN`, not a path on the stick).

## What is stored

| File | Stored as |
|------|-----------|
| `exportLibrary.db`, `export.pdb`, crates, `database V2`, `location.sqlite`, `neworder.pref` | Full copy |
| `.mp3` / `.wav` / `.flac` that we are about to tag | `UVSD1` delta: original tag head/tail + audio hashes |

A destroyed audio stream cannot be rebuilt from a tag delta. That is the
size trade-off: a 200 GB stick does not need a 200 GB backup.

## Procedure

1. Resolve all file paths the operation will touch
2. If the latest timestamped backup already has an identical snapshot of
   every file (size + `original_sha256`), reuse that directory
3. Otherwise create a timestamped backup directory on the host
4. Copy small files; encode audio deltas
5. Compute checksums of the **stored artifacts**
6. Write `manifest.json`
7. Pass `backup_path` into `WriteContext`
8. Proceed with adapter write only after the gate succeeds

An explicit `backup_id` (pre-rollback snapshots) always writes a new
directory. Reuse is only for the automatic timestamp id.

## manifest.json

| Field | Purpose |
|-------|---------|
| `backup_id` | Unique id for rollback |
| `created_at` | ISO timestamp |
| `source_mount` | Original mount path |
| `files` | `{relative_path, sha256, size, kind, stored_as, original_sha256, original_size}` |

`kind` is `full` or `delta`. Checksums are of the artifact in the backup
directory (the `.delta` file, not the song).

## Integrity

- Rekordbox: run `PRAGMA integrity_check` on backup copy before write
- Serato: verify file size/hash matches the stored artifact after copy
- Audio delta: rollback refuses if the current audio hash no longer matches

## Related

- [rollback-flow.md](rollback-flow.md)
- [../adapters/rekordbox.md](../adapters/rekordbox.md)
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
