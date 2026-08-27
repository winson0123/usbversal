# Serato Adapter

**Status:** read-only listing + crate write implemented. Index authoring planned (Stage 1, TASK-071…076); analysis tags planned (Stage 2, TASK-080…085).

## Overview

Serato uses **proprietary on-disk formats** under `_Serato_` directories. This adapter is the only module allowed to interpret Serato binary/text database files.

## Schema Status

As of 2026-08-21 the write formats are **decoded from a byte-exact before/after
fixture pair**, not inferred. Full layouts live in
[../schemas/serato-schema-notes.md](../schemas/serato-schema-notes.md);
fixtures in [`tests/fixtures/serato/`](../../tests/fixtures/serato/).

| Artifact | Confidence |
|----------|------------|
| TLV container (tag / u32 BE length / payload, type from tag prefix) | verified |
| `.crate` structure (`vrsn`, `osrt`, `ovct`, ordered `otrk`) | verified |
| `database V2` `otrk` minimal field set | verified |
| `neworder.pref` (UTF-16BE `[crate]<name>` records) | verified |
| `Serato Markers2` `CUE` layout | verified |
| `Serato BeatGrid` / `Autotags` layout | verified format; no reference writer |
| Path convention (drive-relative, no leading slash) | verified |
| `%%` nested-crate naming | confirmed in Serato (`Gigs%%Played%%safety day`, 2026-08-27) |
| MP3 ID3 container path | **untested** — fixtures are WAV |

Vendor formats still change without notice; treat versions defensively.

## Unknown Fields Tracking

- Parse defensively; store unmapped binary sections or key-value pairs as opaque blobs.
- Never discard unrecognized records when rewriting.
- Document discoveries in `docs/schemas/serato-schema-notes.md`.

## Safety Constraints

| Constraint | Enforcement |
|------------|-------------|
| Backup before write | Full file copy of all touched Serato DB files |
| No in-place patch without backup | Storage layer gate |
| Read-only if parse confidence low | Adapter returns error, does not guess |
| No schema rebuild | Never regenerate entire database from scratch |

## Recommended library: `serato-tools`

| Component | API |
|-----------|-----|
| Library index | `DatabaseV2(file=".../database V2")` → `get_track_paths()` |
| Playlist (= crate) | `Crate(".../Subcrates/Name.crate")` → `get_track_paths()` |

See [../schemas/serato-schema-notes.md](../schemas/serato-schema-notes.md) and [../planning/rekordbox-to-serato-playlist-migration.md](../planning/rekordbox-to-serato-playlist-migration.md).

## Read Operations

| Operation | Status | CLI |
|-----------|--------|-----|
| Resolve `_Serato_` | implemented | |
| List crates + track counts | implemented | |
| List database track index size | implemented | included in `list-crates` output |
| Write crate from Rekordbox playlist | implemented | `migrate-playlist --mount …` |

## Write Operations

| Operation | Status | Task |
|-----------|--------|------|
| Write `.crate` from a Rekordbox playlist | implemented | TASK-033 |
| Back up `neworder.pref` with the rest of `_Serato_` | **gap** | TASK-071 |
| `database V2` append `otrk` | implemented | TASK-112 |
| `neworder.pref` merge / write | planned | TASK-074 |
| `Parent%%Child` nested crate naming | confirmed in Serato | TASK-075 / TASK-245 |
| Bootstrap `_Serato_` on a rekordbox-only stick | planned | TASK-076 |
| `Serato Markers2` hot cues | planned | TASK-082 |
| `Serato BeatGrid` / `Autotags` | planned | TASK-083 |

Rules: merge existing records, never regenerate; preserve unrecognized TLV tags
verbatim; prefer append or field-level edits over full rewrite.

**Do not use `serato_tools.usb_export.copy_crates_to_usb`** — it `rmtree`s the
destination `_Serato_` directory.

## Related

- [../schemas/serato-schema-notes.md](../schemas/serato-schema-notes.md)
- [../planning/serato-index-bootstrap.md](../planning/serato-index-bootstrap.md)
- [../decisions/0007-revive-analysis-sync-on-verified-formats.md](../decisions/0007-revive-analysis-sync-on-verified-formats.md)
- [../decisions/0001-use-python-cli.md](../decisions/0001-use-python-cli.md)
