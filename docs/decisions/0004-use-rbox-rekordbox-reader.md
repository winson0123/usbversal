# ADR 0004: Use rbox for Rekordbox One Library reads

**Status:** accepted  
**Date:** 2026-05-25

## Context

USB Rekordbox exports use multiple on-disk formats:

- `exportLibrary.db` — SQLCipher SQLite (“One Library” / Device Library Plus)
- `export.pdb` — legacy DeviceSQL binary format

Reverse-engineering SQLCipher keys and DeviceSQL page layouts in-house is high-risk and slow. PyPI packages already exist for Rekordbox 6/7 data access.

## Decision

Use **`rbox`** (`OneLibrary`) as the read adapter for `exportLibrary.db` playlist listing.

- Wrap rbox behind `app/adapters/rekordbox/` and map to domain `Playlist` models.
- Keep CLI thin via `app/services/playlist_service.py`.
- Do **not** add a custom DeviceSQL parser in this phase; `export.pdb`-only mounts return `UnsupportedDatabaseError` with a clear message.

## Consequences

### Positive

- Correct decryption and schema access for One Library exports on `/mnt/usb`
- Faster delivery of `list-playlists` with real playlist names and hierarchy
- Maintained upstream fixes for Rekordbox format changes

### Negative

- New runtime dependency (`rbox`, SQLCipher wheels)
- Classic `export.pdb`-only USB sticks remain unsupported until a library adds DeviceSQL or we integrate one
- Tests mock rbox for unit tests; live `/mnt/usb` test is optional skip

### Neutral

- `pyrekordbox` was evaluated; installed 0.4.4 lacks `DeviceLibraryPlus` in public API. `rbox` worked immediately on the test device.
- Smart vs manual playlist type is **not modeled** for USB: export materializes tracks; `smart_list` rules are not on `exportLibrary.db`. Documented in schema notes.
