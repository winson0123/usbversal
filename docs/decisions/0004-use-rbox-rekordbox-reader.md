# ADR 0004: Use rbox for Rekordbox One Library reads

**Status:** accepted
**Date:** 2026-05-25

## Context

USB Rekordbox exports show up as two files:

- `exportLibrary.db`, SQLCipher SQLite ("One Library" / Device Library Plus)
- `export.pdb`, DeviceSQL

Cracking SQLCipher keys and DeviceSQL pages by hand is slow and easy
to get wrong. PyPI already has Rekordbox 6/7 readers.

## Decision

Use `rbox` (`OneLibrary`) to read `exportLibrary.db`.

Wrap it in `app/adapters/rekordbox/` and map rows to `Playlist`.
Do not add a DeviceSQL parser. An `export.pdb`-only mount raises
`UnsupportedDatabaseError`. Never write under `PIONEER/`.

## Consequences

One Library exports decrypt and list playlists. Upstream can fix format
changes.

Usbversal depends on `rbox` and SQLCipher wheels. Classic `export.pdb`
sticks stay unsupported.

USB exports already freeze smart playlists into track lists, so the
adapter does not model smart vs manual. That lives in the schema notes.
