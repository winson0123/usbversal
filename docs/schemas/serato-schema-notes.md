# Serato Schema Notes

Accumulated reverse-engineering and tooling notes. **Read validated on `/mnt/usb` via `serato-tools`.**

## Status legend

| Tag | Meaning |
|-----|---------|
| [confirmed] | Verified on test USB or with serato-tools |
| [assumed] | Not verified on disk |
| [unknown] | Needs research |

## Library root [confirmed]

```text
/mnt/usb/_Serato_/
  database V2
  Metadata/              # empty on test USB export
  Subcrates/
    Contents.crate
    Serato Stems/          # optional stems crate dir
```

## database V2 [confirmed]

| Property | Value |
|----------|-------|
| Path | `_Serato_/database V2` |
| Version string | `2.0/Serato Scratch LIVE Database` |
| Parser | `serato_tools.database_v2.DatabaseV2` |
| Track key field | file path (relative, no leading slash) |
| Tracks on test USB | 793 |

Example path:

```text
Contents/Alice Deejay/UnknownAlbum/Alice Deejay - Better Off Alone [Clean].mp3
```

## Crate files (.crate) [confirmed]

| Property | Value |
|----------|-------|
| Format | `1.0/Serato ScratchLive Crate` |
| Parser | `serato_tools.crate.Crate` |
| Track entries | `otrk` chunks with UTF-16 path |
| Default dir | `_Serato_/Subcrates/` |
| Test USB | Single file `Contents.crate` (793 tracks) |

Per-playlist crates on desktop may not all be exported to USB; migration likely **creates new `.crate` files** per target playlist.

## Smart crates [unknown on USB]

| Path | Status |
|------|--------|
| `*.smartcrate` | Not observed on `/mnt/usb` |
| Rules | Use `serato-tools` `SmartCrate` when present on PC library |

## Path alignment with Rekordbox [confirmed]

| Vendor | Path form |
|--------|-----------|
| Rekordbox `content.path` | `/Contents/.../file.mp3` |
| Serato | `Contents/.../file.mp3` |

Normalize: lowercase, `/`, strip leading `/`.

All Serato-indexed tracks on test USB exist in Rekordbox `exportLibrary.db` (793 ⊆ 1625).

## Mutation safety

| Rule | Status |
|------|--------|
| Read-first milestone | policy |
| Backup `_Serato_` before any byte write | required (TASK-011) |
| Use serato-tools `save()` not hand-edited bytes | policy |

## Parser status

| Component | Status |
|-----------|--------|
| `DatabaseV2` read | [confirmed] serato-tools |
| `Crate` read | [confirmed] serato-tools |
| `DatabaseV2` write | [assumed] serato-tools supports save |
| `Crate` write | [assumed] serato-tools `add_track`, `save` |
| Usbversal adapter | planned (TASK-031) |

## Related

- [../planning/rekordbox-to-serato-playlist-migration.md](../planning/rekordbox-to-serato-playlist-migration.md)
- [../adapters/serato.md](../adapters/serato.md)
