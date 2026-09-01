# Serato adapter

This package is the only place that may read or write `_Serato_` files.

We write crates, append `database V2`, UPDATE existing `location.sqlite`
rows, and write analysis tags.

## Writes

| Artifact | Action |
|----------|--------|
| `Subcrates/*.crate` | Write or replace from a Rekordbox playlist |
| `database V2` | Append `otrk` for tracks Serato does not already index |
| `neworder.pref` | Merge crate display order |
| Volume-label parent crate | Empty folder node so Serato shows the tree |
| Audio GEOB tags | `Serato BeatGrid`, `Serato Markers2`, and v1 markers |
| `_Serato_/Library/location.sqlite` | UPDATE `bpm`, `key`, `analysis_flags` (24) on existing rows only |

## Never

- Write under `PIONEER/`
- Create `location.sqlite` or insert rows
- Rebuild `database V2` from scratch
- Drop unrecognized TLV tags on rewrite

## Naming

Nested Rekordbox folders become `Parent%%Child.crate`. A slash in a
playlist name is Serato's crate-name escape, not a folder. Leftover
fullwidth-slash crate files from an older spelling are deleted on write.

## Tag rewrite

Skip the write when the payload already matches. Verify hash and
read-back. Patch in place when the size stays the same. WAV grows after
`data` when it can. Otherwise write a `.tmp` and replace. Restore the
original file if replace fails.

## serato-tools

| Piece | Call |
|-------|------|
| Library index | `DatabaseV2` → `get_track_paths()` |
| Crate | `Crate` → `get_track_paths()` |

Layouts: [../schemas/serato-schema-notes.md](../schemas/serato-schema-notes.md).
