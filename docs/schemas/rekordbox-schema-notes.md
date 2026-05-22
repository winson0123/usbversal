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

## Real device validation (`/mnt/usb`)

| Item | Recorded |
|------|----------|
| export.pdb path | _pending agent scan_ |
| table list | _pending_ |
| rekordbox version | _pending_ |

> Update this section after first safe read-only scan of `/mnt/usb`.
