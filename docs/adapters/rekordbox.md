# Rekordbox adapter

Read-only One Library (`exportLibrary.db`) through rbox. This package
never writes under `PIONEER/`.

## Formats

| File | Format | Reader |
|------|--------|--------|
| `PIONEER/rekordbox/exportLibrary.db` | SQLCipher One Library | `rbox` (ADR 0004) |
| `PIONEER/rekordbox/export.pdb` | DeviceSQL | Unsupported. Clear error. |

## Reads

| Operation | What happens |
|-----------|----------------|
| Resolve DB path | Prefers `exportLibrary.db` |
| List playlists | `rbox.OneLibrary` → domain `Playlist` |
| Playlist track paths | Ordered Rekordbox content paths |
| Content and lookup tables | Sync builds Serato records from these |

Rekordbox rebuilds "CUE Analysis Playlist" on every export. We omit it.

USB One Library already freezes smart playlists into track lists. We do
not classify smart vs manual. See
[../schemas/rekordbox-schema-notes.md](../schemas/rekordbox-schema-notes.md).

## Safety

| Rule | What we do |
|------|------------|
| Rekordbox files | Never write under `PIONEER/` |
| Schema rebuild | Never `DROP` or `CREATE` wholesale |
| Locked DB | Fail clearly. Do not guess. |
