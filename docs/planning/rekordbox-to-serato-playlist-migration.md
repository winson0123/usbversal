# Rekordbox → Serato Playlist Migration (Planning)

**Status:** implemented (`migrate-playlist` CLI, TASK-033)  
**Related:** TASK-031, TASK-012, TASK-033

## Goal

Copy playlist **membership** from Rekordbox USB export (`exportLibrary.db`) into Serato USB export (`_Serato_/`), without touching audio files under `Contents/`.

## What We Learned on `/mnt/usb` (2026-05-25)

### Serato layout [confirmed]

```text
/mnt/usb/_Serato_/
  database V2          # Library index (~793 tracks on test USB)
  Metadata/            # Empty on this export
  Subcrates/
    Contents.crate     # Single crate, 793 tracks (device “all contents” style)
    Serato Stems/        # Stems crate path (empty here)
```

| Artifact | Format | Tooling |
|----------|--------|---------|
| `database V2` | Serato binary DB v2 (`2.0/Serato Scratch LIVE Database`) | `serato-tools` `DatabaseV2` |
| `*.crate` | Serato ScratchLive Crate v1 (`otrk` + UTF-16 paths) | `serato-tools` `Crate` |
| `*.smartcrate` | Smart rules | Not present on test USB |

### Rekordbox layout [confirmed]

| Artifact | Format | Tooling |
|----------|--------|---------|
| `exportLibrary.db` | SQLCipher One Library | `rbox` `OneLibrary` |
| Playlists | `playlist` + `playlist_content` tables | `get_playlists()`, `get_playlist_contents(id)` |

### Track path alignment [confirmed]

| Source | Path example |
|--------|----------------|
| Rekordbox `content.path` | `/Contents/Alice Deejay/.../track.mp3` |
| Serato `database V2` | `Contents/Alice Deejay/.../track.mp3` |

Normalize: lowercase, forward slashes, **strip leading `/`**.

On test USB:

- Serato DB: **793** tracks  
- Rekordbox library: **1625** tracks  
- **All 793 Serato paths ⊆ Rekordbox** (100% of Serato index exists in Rekordbox export)

So playlist→crate migration on the **same USB** can match by path; Rekordbox-only tracks can still be listed but would not resolve in Serato until exported/synced to the stick.

## Conceptual Mapping

| Rekordbox | Serato |
|-----------|--------|
| Playlist folder (`is_folder`) | Subfolder under `Subcrates/` or crate naming convention |
| Playlist (`List`) | One `Subcrates/<Name>.crate` file |
| `playlist_content` rows | `otrk` entries in `.crate` (ordered) |
| `content.path` | Must exist in `database V2` (or add track — out of scope initially) |

**Not mapped on USB export:**

- Rekordbox smart playlists (rules not on stick; baked lists only)
- Serato smart crates (`.smartcrate`) — none observed
- Crate hierarchy (Serato crates are flat files; RB folders → multiple `.crate` files or naming)

## Recommended Tooling

| Library | Use |
|---------|-----|
| **`rbox`** | Read RB playlists + `get_playlist_contents(playlist_id)` + `content.path` |
| **`serato-tools`** | Read/write `database V2`, create/modify `.crate` files |

Evaluate ADR before adding `serato-tools` as a dependency (mirror ADR 0004 for `rbox`).

## Pipeline (Implemented)

```text
1. backup_mount_for_migration()     # Rekordbox DBs + Serato database V2 + all .crate files
2. Read RB playlist                 # rbox get_playlist_contents → content.path
3. Normalize paths                  # app/core/track_paths.py
4. Filter to Serato DB              # database V2 index lookup
5. write_crate()                    # Subcrates/<PlaylistName>.crate via serato-tools
6. CLI reports matched/skipped counts
```

```bash
python -m app.cli migrate-playlist --mount /mnt/usb --playlist-id 1 --dry-run
python -m app.cli migrate-playlist --mount /mnt/usb --playlist-name "Pocket" --overwrite
```

## Risks

| Risk | Mitigation |
|------|------------|
| Path mismatch (truncated Serato paths) | Compare lengths; log warnings (Serato truncates long names on export) |
| Duplicate `database V2` entries | Use Serato APIs; do not hand-edit binary |
| Writing without backup | `WriteContext` + backup `_Serato_` before any save |
| RB playlist > Serato indexed tracks | Report skipped tracks; do not silently drop |
| Single `Contents.crate` vs new crates | Prefer **new crate per RB playlist**; do not rewrite `Contents.crate` without explicit flag |

## TASK-031 (Done)

- `list-crates --mount /mnt/usb` via `serato-tools` (ADR 0005)
- Crate names + track counts + `database V2` index size

## Task Status

| ID | Work | Status |
|----|------|--------|
| TASK-031 | Serato read-only: list crates + DB stats | done |
| TASK-012 | Rollback (safety) | done |
| TASK-033 | `migrate-playlist` CLI (path match + crate write) | done |
| TASK-034 | `sync-analysis` CLI (BPM/key/cues/beatgrid → MP3 tags) | done |
| TASK-053 | Generic `apply` plan format tying both vendors | backlog |

## Open Questions

1. Should migrated playlists appear as **new `.crate` files** or merge into an existing crate?
2. Are duplicate track variants (`-1` suffix) intentional on Serato export — dedupe when copying?
3. Does the DJ software re-scan `database V2` when only `.crate` files change?
