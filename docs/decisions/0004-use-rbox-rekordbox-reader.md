# ADR 0004: Use rbox for Rekordbox One Library reads

**Status:** accepted
**Date:** 2026-05-25

## Context

USB Rekordbox exports use multiple on-disk formats:

- `exportLibrary.db` — SQLCipher SQLite (“One Library” / Device Library Plus)
- `export.pdb` — DeviceSQL binary format

Reverse-engineering SQLCipher keys and DeviceSQL page layouts in-house is
high-risk and slow. PyPI packages already exist for Rekordbox 6/7 data access.

## Decision

Use **`rbox`** (`OneLibrary`) as the read adapter for `exportLibrary.db`.

- Wrap rbox behind `app/adapters/rekordbox/` and map to domain `Playlist` models.
- Do **not** add a DeviceSQL parser; `export.pdb`-only mounts return
  `UnsupportedDatabaseError`.
- Never write under `PIONEER/`.

## Consequences

### Positive

- Correct decryption and schema access for One Library exports
- Maintained upstream fixes for Rekordbox format changes

### Negative

- Runtime dependency (`rbox`, SQLCipher wheels)
- Classic `export.pdb`-only USB sticks remain unsupported

### Neutral

- Smart vs manual playlist type is not modeled for USB: the export
  materializes tracks. Documented in schema notes.
