# Serato Adapter

**Status:** crate write, `database V2` append, `location.sqlite` UPDATE, and
analysis tag writes are implemented.

## Overview

Serato uses proprietary on-disk formats under `_Serato_`. This adapter is
the only module allowed to interpret those files.

## What we write

| Artifact | Action |
|----------|--------|
| `Subcrates/*.crate` | Write / replace from a Rekordbox playlist |
| `database V2` | Append `otrk` for tracks Serato does not already index |
| `neworder.pref` | Merge crate display order |
| Volume-label parent crate | Empty folder node so Serato shows the tree |
| Audio GEOB tags | `Serato BeatGrid`, `Serato Markers2` (and v1 markers) |
| `_Serato_/Library/location.sqlite` | UPDATE `bpm`, `key`, `analysis_flags` (24) on existing rows only |

## What we never do

- Write under `PIONEER/`
- Create `location.sqlite` or insert rows into it
- Regenerate `database V2` from scratch
- Discard unrecognized TLV tags on rewrite

## Naming

Nested Rekordbox folders become `Parent%%Child.crate`. A slash in a
playlist name is Serato's crate-name escape, not a folder. Leftover
fullwidth-slash crate files from an earlier spelling are deleted on write.

## Tag rewrite

Tag-only skip when the payload already matches; verify hash and
read-back; same-size patch when possible; WAV tail rewrite after `data`;
else `.tmp` then replace. Restore the original file if replace fails.

## Recommended library: `serato-tools`

| Component | API |
|-----------|-----|
| Library index | `DatabaseV2` → `get_track_paths()` |
| Crate | `Crate` → `get_track_paths()` |

Layouts: [../schemas/serato-schema-notes.md](../schemas/serato-schema-notes.md).
