# Backup Strategy

**Status:** implemented (content-addressed objects + thin snapshots).

## Principle

**No database or audio-tag write without a verified backup.**

Backups live on the **host**, not the USB. Each artifact is stored once
under `objects/<sha256>`. A snapshot is a `manifest.json` that names those
objects. Audio is a tag-region delta (`UVSD1`), not a second copy of the
song.

Default root:

| OS | Path |
|----|------|
| Linux / macOS | `~/.local/share/usbversal/backups/<volume>/` |
| Windows | `%LOCALAPPDATA%/usbversal/backups/<volume>/` |

Override with `USBVERSAL_BACKUP_ROOT`. Volume is the mount folder name
(`WONSIN`, not a path on the stick).

## Layout

```text
<volume>/
  latest                         # backup_id of the current snapshot
  error.log                      # last sync failures
  objects/<sha256>               # full copies and UVSD1 deltas, stored once
  20260829T080257Z/manifest.json # one snapshot; lists relative_path -> object
```

If one file changes, a new snapshot directory is created and **only that
file's blob** is added to `objects/`. Unchanged files keep the same hash
in the new manifest.

When every file in the run still matches the latest snapshot, that
snapshot is reused and no new directory is created.

An explicit `backup_id` (pre-rollback snapshots) always writes a new
directory. Reuse is only for the automatic timestamp id.

Older snapshots that copied files into the timestamp folder still verify
and roll back; new writes use `objects/`.

## What is stored

| File | Stored as |
|------|-----------|
| `exportLibrary.db`, `export.pdb`, crates, `database V2`, `location.sqlite`, `neworder.pref` | Full object (`objects/<sha256>`) |
| `.mp3` / `.wav` / `.flac` that we are about to tag | `UVSD1` delta object: original tag head/tail + audio hashes |

A destroyed audio stream cannot be rebuilt from a tag delta. That is the
size trade-off: a 200 GB stick does not need a 200 GB backup.

## Procedure

1. Resolve all file paths the operation will touch
2. If the latest snapshot already has an identical copy of every file
   (size + `original_sha256`), reuse that directory
3. Otherwise create a timestamped snapshot directory
4. For each file: reuse the previous object when the live bytes match;
   otherwise write a new object
5. Write `manifest.json` and update `latest`
6. Pass `backup_path` into `WriteContext`
7. Proceed with adapter write only after the gate succeeds

## manifest.json

| Field | Purpose |
|-------|---------|
| `backup_id` | Unique id for rollback |
| `created_at` | ISO timestamp |
| `source_mount` | Original mount path |
| `files` | `{relative_path, sha256, size, kind, stored_as, original_sha256, original_size}` |

`kind` is `full` or `delta`. `stored_as` is `objects/<sha256>` for new
writes. Checksums are of the stored artifact (the object, not the song).

## Integrity

- Rekordbox: run `PRAGMA integrity_check` on backup copy before write
- Serato: verify file size/hash matches the stored artifact after copy
- Audio delta: rollback refuses if the current audio hash no longer matches

## Related

- [rollback-flow.md](rollback-flow.md)
- [../adapters/rekordbox.md](../adapters/rekordbox.md)
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
