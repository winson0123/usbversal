# Rekordbox Schema Notes

Accumulated reverse-engineering. **Do not treat as complete.**

## Status legend

| Tag | Meaning |
|-----|---------|
| [confirmed] | Verified in fixture or test |
| [assumed] | Industry/docs hint, not verified on USB |
| [unknown] | Not yet observed |

## Observed tables

| Table | Source | Tag |
|-------|--------|-----|
| _none yet_ | awaiting fixtures | [unknown] |

## Detection heuristic (planned)

| Condition | `version_label` |
|-----------|-----------------|
| `djmdContent` present | `rekordbox-sqlite-djmd` |
| else | `rekordbox-sqlite-unknown` |

## Planned tables (assumed — verify on real DB)

| Table | Purpose | Tag |
|-------|---------|-----|
| `djmdPlaylist` | Playlists | [assumed] |
| `djmdSongPlaylist` | Playlist membership | [assumed] |
| `djmdArtist` | Artist metadata | [assumed] |
| `djmdContent` | Track rows | [assumed] |

## Relationships (inferred)

```text
djmdPlaylist ──< djmdSongPlaylist >── djmdContent
```

**Tag:** [assumed] — verify with `PRAGMA foreign_key_list` on real DB.

## Unknown fields policy

| Rule | Status |
|------|--------|
| SELECT known columns only | planned |
| Never write NULL to unknown columns | planned |
| Log unseen columns on read | planned |

## Mutation safety

| Operation | Notes |
|-----------|-------|
| INSERT playlist row | needs backup + transaction |
| UPDATE track metadata | preserve unmapped columns |
| DELETE | avoid unless explicit user op |

## One Library export (`exportLibrary.db`) [confirmed]

Read via `rbox.OneLibrary` on `/mnt/usb` (2026-05-25):

| Table (rbox) | Purpose |
|--------------|---------|
| `playlist` | Playlist/folder nodes (`attribute`, `parent_id`, `name`) |
| `playlist_content` | Track membership snapshot |

`playlist.attribute` (rbox `PlaylistType`): `List` (0), `Folder` (1), `SmartList` (4).

Observed on test USB: **64 List, 6 Folder, 0 SmartList**.

## Smart playlists vs normal playlists on USB [confirmed]

**Do not distinguish smart vs manual playlists for USB export workflows.**

Rekordbox’s intended export behavior is to ship a **snapshot** for the player:

- Tracks are materialized in `playlist_content`.
- The export `playlist` row has **no `smart_list` rules column** (unlike `master.db` / `djmdPlaylist`).
- Desktop “intelligent playlists” often appear as `List` (0) on the stick even when smart in the PC library.
- `SmartList` (4) may be absent entirely on export (true for `/mnt/usb`).

Usbversal treats exported nodes as **folder** vs **playlist (list)** only. Rule-based refresh belongs on `master.db`, not USB tooling.

## Real device validation (`/mnt/usb`)

| Item | Recorded |
|------|----------|
| exportLibrary.db | `/mnt/usb/PIONEER/rekordbox/exportLibrary.db` [confirmed, 70 playlist nodes] |
| export.pdb path | `/mnt/usb/PIONEER/rekordbox/export.pdb` [confirmed scan 2026-05-25, DeviceSQL] |
| PIONEER/rekordbox dir | `/mnt/usb/PIONEER/rekordbox` [confirmed] |
| Contents/rekordbox | `/mnt/usb/Contents/rekordbox` [confirmed, lower confidence] |
| rekordbox version | _pending_ |
