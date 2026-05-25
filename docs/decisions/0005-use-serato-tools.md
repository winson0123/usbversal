# ADR 0005: Use serato-tools for Serato reads

**Status:** accepted  
**Date:** 2026-05-25

## Context

Serato on USB uses `database V2` (binary library index) and `Subcrates/*.crate` (playlist files). Hand-parsing `otrk` chunks and the database format is high-risk. PyPI package **serato-tools** supports read/write for both, validated on `/mnt/usb`.

## Decision

Use **serato-tools** (`DatabaseV2`, `Crate`) behind `app/adapters/serato/` for read-only crate listing (TASK-031) and future crate creation for Rekordbox→Serato migration.

## Consequences

### Positive

- Correct parsing of `database V2` and `.crate` on test hardware
- Path for future `Crate.save()` / `add_track` with backup gating
- Aligns with ADR 0004 approach (vendor library behind thin adapter)

### Negative

- Additional dependency; requires Python 3.12+ per upstream (works on 3.13 in dev)
- Write paths must still enforce backup before `save()`

### Neutral

- Smart crates (`.smartcrate`) not on USB export; out of scope until observed on disk
