# Serato Schema Notes

Accumulated reverse-engineering. **Not implemented — placeholder only.**

## Status legend

| Tag | Meaning |
|-----|---------|
| [confirmed] | Verified in code/test |
| [assumed] | Not verified on disk |
| [unknown] | Needs research |

## Known paths (assumed)

| Path | Purpose | Tag |
|------|---------|-----|
| `_Serato_/` | Library root | [assumed] |
| `database V2` | Track database | [assumed] |
| `Subcrates/` | `.crate` files | [assumed] |

## Parser status

| Component | Status |
|-----------|--------|
| Binary parse | [unknown] |
| SQLite variant | [unknown] |
| Adapter stub | planned |

## Mapping to domain

| Serato | Usbversal |
|--------|-----------|
| Crate file | `Crate` |
| Track entry | `TrackMetadata` |
| Playlist | TBD (Serato DJ differs from crates) | [unknown] |

## Mutation safety

| Rule | Status |
|------|--------|
| Read-first milestone | policy |
| Backup before any byte write | policy |
| No in-place experiment on `/mnt/usb` | policy |

## Real device validation (`/mnt/usb`)

| Item | Recorded |
|------|----------|
| `_Serato_` present | `/mnt/usb/_Serato_` [confirmed scan 2026-05-25] |
| Subcrates | `/mnt/usb/_Serato_/Subcrates` (.crate files) [confirmed] |
| Format version | _pending adapter read_ |
