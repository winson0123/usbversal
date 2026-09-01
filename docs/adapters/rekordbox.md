# Rekordbox Adapter

**Status:** read-only One Library (`exportLibrary.db`) via **rbox**.

## Overview

This adapter isolates Rekordbox access and schema mapping from core
domain logic. It never writes under `PIONEER/`.

## Supported formats

| File | Format | Reader |
|------|--------|--------|
| `PIONEER/rekordbox/exportLibrary.db` | SQLCipher One Library | `rbox` (ADR 0004) |
| `PIONEER/rekordbox/export.pdb` | DeviceSQL | **unsupported** — clear error |

## Read operations

| Operation | Status |
|-----------|--------|
| Resolve DB path | Prefers `exportLibrary.db` |
| List playlists | `rbox.OneLibrary` → domain `Playlist` |
| Playlist track paths | Ordered Rekordbox content paths |
| Content / lookup tables | Used by sync to build Serato records |

Rekordbox's regenerated **CUE Analysis Playlist** is omitted from the tree.

## Smart playlists

USB One Library export materializes tracks. Usbversal does not classify
smart vs manual on USB. See [../schemas/rekordbox-schema-notes.md](../schemas/rekordbox-schema-notes.md).

## Safety

| Constraint | Enforcement |
|------------|-------------|
| Rekordbox files | Never write under `PIONEER/` |
| No schema rebuild | Never `DROP` / `CREATE` wholesale |
| Locked DB | Fail clearly; do not guess |
