# Rekordbox Adapter

**Status:** read-only playlists implemented for One Library (`exportLibrary.db`) via **rbox**.

## Overview

Rekordbox stores library metadata primarily in **SQLite** databases on USB/export media. This adapter isolates all SQLite access and schema mapping from core domain logic.

## Schema Assumptions (Tentative)

| Assumption | Confidence | Notes |
|------------|------------|-------|
| Primary DB is `export.pdb` or similar SQLite file | high | Version-dependent path |
| Playlist hierarchy in relational tables | medium | Table names vary by Rekordbox version |
| Track metadata keyed by internal ID | high | |
| Schema changes between minor versions | high risk | Must detect, not hardcode |

**Do not treat this table as authoritative** until validated against real USB exports.

## Unknown Fields Tracking

- On read: preserve columns not mapped to domain models in `unknown_fields` bag.
- On write: never drop unknown columns; pass through or skip write for unmapped tables.
- Log `adapter.unknown_field` events for documentation updates in `docs/schemas/`.

## Safety Constraints

| Constraint | Enforcement |
|------------|-------------|
| Rekordbox files | Never write under `PIONEER/` |
| Integrity check | `PRAGMA integrity_check` before and after write (when possible) |
| No schema rebuild | Never `DROP`/`CREATE` wholesale |
| Locked DB | Detect `-wal`/`-shm` or lock files; warn, prefer read-only |
| DJ software running | Warn if Rekordbox process detected (platform-specific, future) |

## Read Operations

| Operation | Status | Notes |
|-----------|--------|-------|
| Resolve DB path | implemented | Prefers `exportLibrary.db`, falls back detection of `export.pdb` |
| List playlists | implemented | `rbox.OneLibrary` → domain `Playlist` models |
| Read track metadata | planned | Not in TASK-030 scope |

### Supported formats

| File | Format | Reader |
|------|--------|--------|
| `PIONEER/rekordbox/exportLibrary.db` | SQLCipher One Library | `rbox` (ADR 0004) |
| `PIONEER/rekordbox/export.pdb` | DeviceSQL | **unsupported** — clear error |

### Smart playlists (out of scope on USB)

Rekordbox PC libraries can have **intelligent playlists** (`PlaylistType.SmartList`, `smart_list` rules in `master.db`). USB **One Library** export is not meant to preserve that distinction: playlists are exported as a **frozen track list** (`playlist` + `playlist_content`). Genre-style lists on `/mnt/usb` use `List` (0), not `SmartList` (4).

**Policy:** Usbversal does not classify smart vs manual on USB. See [../schemas/rekordbox-schema-notes.md](../schemas/rekordbox-schema-notes.md).

## Write Operations (Planned)

- Apply domain `Plan` objects (playlist moves, metadata edits)
- Transactional writes where SQLite allows
- Recovery is restoring the Rekordbox USB

## Related

- [../schemas/rekordbox-schema-notes.md](../schemas/rekordbox-schema-notes.md)
- [../storage/usb-detection.md](../storage/usb-detection.md)
