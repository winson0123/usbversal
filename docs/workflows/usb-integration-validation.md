# USB Integration Validation (`/mnt/usb`)

**Task:** TASK-061  
**Last validated:** 2026-06-05  
**Environment:** WSL2, mount `/mnt/usb`

Manual and CLI validation of the Rekordbox → Serato playlist migration workflow on real USB hardware. Serato **Analyze Files** is required after migration (analysis tag sync is deferred; see [ADR 0006](../decisions/0006-serato-analyzed-and-beatgrid-tags.md)).

## Prerequisites

- USB stick mounted at `/mnt/usb` (read-write for writes)
- Project venv: `.venv/bin/python -m app.cli`
- Rekordbox One Library export: `PIONEER/rekordbox/exportLibrary.db`
- Serato library: `_Serato_/database V2`

## End-to-end workflow

```bash
# 1. Discover libraries
.venv/bin/python -m app.cli scan --mount /mnt/usb

# 2. Inspect Rekordbox playlists
.venv/bin/python -m app.cli list-playlists --mount /mnt/usb

# 3. Inspect Serato crates
.venv/bin/python -m app.cli list-crates --mount /mnt/usb

# 4. Plan migration (no writes)
.venv/bin/python -m app.cli migrate-playlist --mount /mnt/usb --playlist-name "Pocket" --dry-run

# 5. Migrate (creates backup, writes Subcrates/<name>.crate)
.venv/bin/python -m app.cli migrate-playlist --mount /mnt/usb --playlist-name "Pocket" --overwrite

# 6. In Serato DJ (offline): Analyze Files on the crate/library
```

## Validation results (2026-06-05)

| Step | Command | Result |
|------|---------|--------|
| Scan | `scan --mount /mnt/usb` | Rekordbox + Serato detected at stick root (~36 s; also matches copies under `backups/`) |
| List playlists | `list-playlists --mount /mnt/usb` | **70** playlists; `Pocket` id=1 |
| List crates | `list-crates --mount /mnt/usb` | **1** crate: `Pocket` (80 tracks); Serato DB **793** tracks indexed |
| Migrate dry-run | `migrate-playlist … Pocket --dry-run` | **80/80** paths matched, **0** skipped |
| Unit tests | `pytest` | **49** passed (includes `/mnt/usb` integration when mounted) |

### Library counts

| Source | Count |
|--------|-------|
| Rekordbox `content` rows | 1625 |
| Serato `database V2` index | 793 |
| Pocket playlist (Rekordbox) | 80 tracks |
| Pocket crate (Serato) | 80 tracks |

All Serato-indexed paths on this stick are a subset of Rekordbox export paths (793 ⊆ 1625).

## Manual Serato steps (operator)

After `migrate-playlist`:

1. Eject USB safely from WSL/host if needed; attach to Serato machine.
2. Open Serato DJ in **offline mode** (hardware disconnected).
3. Open the **Pocket** crate (or rescan library if crate not visible).
4. Run **Analyze Files** (Library + Display → analyze settings as desired).
5. Optional: **Rescan ID3 Tags** if tags were edited externally.

Usbversal does **not** copy BPM, beatgrid, or hot cues; Serato analysis is the source of truth for playback metadata.

## Known quirks

| Quirk | Notes |
|-------|-------|
| `scan` walks `backups/` | Each backup under `<mount>/backups/` contains mirrored `PIONEER/` and `_Serato_/` trees; scan reports many duplicate library detections. Prefer `--mount` + targeted commands for operations. |
| Crate name = playlist name | `migrate-playlist` writes `Subcrates/<playlist_name>.crate`; use `--overwrite` to replace an existing crate. |
| Path truncation | Long filenames may differ between Rekordbox and Serato export; migration logs skipped paths when Serato DB has no match. |
| WAV in playlist | One Pocket track is `.wav`; Serato analyze handles format-specific tags. |

## Rollback

If migration needs undoing:

```bash
.venv/bin/python -m app.cli rollback --mount /mnt/usb --backup-id <timestamp>
```

Restores Rekordbox + Serato **database/crate files** from backup; does not revert audio file ID3 tags if those were modified separately.

## Related

- [verification-workflow.md](verification-workflow.md)
- [../planning/rekordbox-to-serato-playlist-migration.md](../planning/rekordbox-to-serato-playlist-migration.md)
- [../storage/usb-detection.md](../storage/usb-detection.md)
