# Rekordbox Adapter

**Status:** placeholder — not implemented.

## Overview

Rekordbox stores library metadata primarily in **SQLite** databases on USB/export media. This adapter isolates all SQLite access and schema mapping from core domain logic.

## Schema Assumptions (Tentative)

| Assumption | Confidence | Notes |
|------------|------------|-------|
| Primary DB is `export.pdb` or similar SQLite file | high | Version-dependent path |
| Playlist hierarchy in relational tables | medium | Table names vary by Rekordbox version |
| Track metadata keyed by internal ID | high | |
| Schema changes between minor versions | high risk | Must detect, not hardcode |

**Do not treat this table as authoritative** until validated against real exports on `/mnt/usb`.

## Unknown Fields Tracking

- On read: preserve columns not mapped to domain models in `unknown_fields` bag.
- On write: never drop unknown columns; pass through or skip write for unmapped tables.
- Log `adapter.unknown_field` events for documentation updates in `docs/schemas/`.

## Safety Constraints

| Constraint | Enforcement |
|------------|-------------|
| Backup before write | `WriteContext.backup_path` required |
| Integrity check | `PRAGMA integrity_check` before and after write (when possible) |
| No schema rebuild | Never `DROP`/`CREATE` wholesale |
| Locked DB | Detect `-wal`/`-shm` or lock files; warn, prefer read-only |
| DJ software running | Warn if Rekordbox process detected (platform-specific, future) |

## Read Operations (Planned)

- Detect library root via `export.pdb` signature
- List playlists and folders
- Read track metadata (no audio file modification)

## Write Operations (Planned)

- Apply domain `Plan` objects (playlist moves, metadata edits)
- Transactional writes where SQLite allows
- Rollback via storage layer on failure

## Related

- [../schemas/rekordbox-schema-notes.md](../schemas/rekordbox-schema-notes.md)
- [../storage/backup-strategy.md](../storage/backup-strategy.md)
