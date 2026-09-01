# ADR 0010: Tolerate a leftover Markers2 base64 character

**Status:** accepted
**Date:** 2026-08-28

## Context

Syncing WONSIN aborted with:

```text
Invalid base64-encoded string: number of data characters (69)
cannot be 1 more than a multiple of 4
```

`_write_track_tags` reads the existing `Serato Markers2` GEOB so
`COLOR` / `BPMLOCK` can be kept while cues are replaced from Rekordbox.
Python 3.11+ `base64.b64decode` rejects a data length of `4n+1`.

A Contents-crate scan found **23 MP3s** with that leftover. The exact
69-character body that matched the error (Thank u, next):

```text
AQFDT0xPUgAAAAAEAP///0NVRQAAAAAOAAAAAABCAMwAAAAAOABCUE1MT0NLAAAAAAEAA
```

## Findings

- **69 = 17×4 + 1.** One character past a valid group. We drop that one
  character (`69 → 68`), not a cut at 64.
- After the drop, the decode is complete: `COLOR`, one `CUE`, `BPMLOCK`.
  No bytes remain. Cutting at 64 would truncate `BPMLOCK`.
- One extra base64 character cannot encode an extra byte (that needs two
  characters). Dropping it removes no decoded field.
- The leftover sat in the GEOB's base64 text, after a finished tag and
  before Serato's `NUL` padding. The same files also carry Serato's own
  analysis set (`Analysis`, `Autotags`, `BeatGrid`, `Markers_`,
  `Offsets_`, `Overview`). Rekordbox ANLZ was not the source. Sync died
  on read, so Usbversal did not write the leftover.
- Pool-distributed tracks (e.g. BPM Supreme edits) often arrive with
  these frames already on the file.

## Decision

`_decode_serato_b64` drops one leftover alphabet character when
`len % 4 == 1`. A remaining `binascii.Error` becomes an empty marker
list so one dirty tag cannot abort the run. The next write replaces
cues from Rekordbox and keeps whatever `COLOR` / `BPMLOCK` decoded.

## Consequences

A track with this leftover still syncs. Its existing Serato colour and
BPM-lock survive. Cue bodies that were already complete stay readable
until we overwrite them from Rekordbox.
