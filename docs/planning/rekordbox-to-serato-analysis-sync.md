# Rekordbox → Serato Analysis Sync

**Status:** implemented (`sync-analysis` CLI)  
**Related:** [rekordbox-to-serato-playlist-migration.md](rekordbox-to-serato-playlist-migration.md)

## Why playlist copy is not enough

`migrate-playlist` only writes **crate membership** (`Subcrates/*.crate`). Serato DJ reads **BPM, key, beatgrid, and hot cues from ID3 tags on each MP3**, not from `database V2`.

| Data | Rekordbox on USB | Serato on USB |
|------|------------------|---------------|
| Playlist membership | `exportLibrary.db` | `.crate` files |
| BPM / gain | `content.bpmx100`, ANLZ | `GEOB:Serato Autotags`, `TBPM` |
| Musical key | `content.key_id` → `key` table | `TKEY` (Camelot, e.g. `8B`) |
| Beatgrid | `PIONEER/USBANLZ/.../ANLZ0000.DAT` | `GEOB:Serato BeatGrid` |
| Hot cues | ANLZ `CueList` | `GEOB:Serato Markers2` |
| Waveform overview | ANLZ waveform tags | `GEOB:Serato Overview` |

On test USB (Pocket playlist, n=80): **all 80** tracks have Rekordbox ANLZ; only **~15** had Serato GEOB tags before sync.

## CLI

```bash
# Preview what would be written
python -m app.cli sync-analysis --mount /mnt/usb --playlist-id 1 --dry-run

# Backup library files + write tags for each track in the playlist
python -m app.cli sync-analysis --mount /mnt/usb --playlist-name "Pocket"
```

## What is copied (v1)

- BPM → Serato Autotags + `TBPM`
- Key → `TKEY` (Camelot mapped from Rekordbox `Key.name`)
- Beatgrid → sparse Serato grid from first ANLZ beat + RB tempo
- Hot cues / loops → Serato Markers2 cue entries

## Not copied (v1)

- Waveform preview/detail (`GEOB:Serato Overview`) — separate binary encode
- Serato `database V2` rows (path index unchanged)
- Rekordbox memory cues (only hot cue list in ANLZ)
- `Contents.crate` or other crates

## Safety

- `backup_mount_for_migration` before writes (Rekordbox + Serato DBs)
- Additional `*-mp3` backup batch for touched audio files
- Use `rollback` if a restore is needed

## Risks

| Risk | Mitigation |
|------|------------|
| Wrong beatgrid shape | Sparse 2-marker grid; re-analyze in Serato if needed |
| Key notation mismatch | Explicit `REKORDBOX_KEY_TO_CAMELOT` table; log unmapped keys |
| MP3 tag corruption | Backup MP3s; mutagen save only |
