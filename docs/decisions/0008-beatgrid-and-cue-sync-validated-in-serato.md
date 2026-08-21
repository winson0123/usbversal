# ADR 0008: Beatgrid and hot cue sync validated in Serato

**Status:** accepted
**Date:** 2026-08-21
**Supersedes:** the beatgrid caution in [ADR 0007](0007-revive-analysis-sync-on-verified-formats.md)

## Context

ADR 0007 revived analysis sync but held beatgrids at arm's length, reasoning
that Lexicon never writes them, so there was no known-good output to test
against. Writing cues had an oracle; writing beatgrids appeared to have none.

That reasoning looked for the wrong oracle.

## What changed

**Rekordbox's own beat data is the oracle.** `PQTZ` holds one entry per beat
with tempo and time. Collapsing runs of equal tempo into markers, with the last
carrying the BPM, reproduces the `Serato BeatGrid` frame already present on
`Techno1-1.wav` byte for byte:

```text
existing Serato BeatGrid : 010000000001000000004308000000
generated from rekordbox : 010000000001000000004308000000
```

**Serato accepted the result.** The `test` playlist was synced to the stick on
2026-08-21 — crate, database records, hot cues, and beatgrids — and confirmed in
Serato: beatgrids correct with no jump, cues landing on beats, and the tracks
showing as analysed.

## What the earlier evidence actually was

Generated grids differed from the existing frames on 60 of 60 sampled MP3s,
which initially read as the generator being wrong. It was the reverse. Every one
of those files carries a non-terminal marker at the first beat with
`beats_to_next = 4` and a terminal at exactly first beat **+ 120.0000 s**,
implying `4 / 120 x 60 = 2.00` BPM for the opening bar.

That is precisely the failure [ADR 0006](0006-serato-analyzed-and-beatgrid-tags.md)
documented. **79 files on the stick still carry it** — the size of the Pocket
playlist used in that abandoned experiment. They are its leftovers, not a
reference. Of 596 files carrying a beatgrid, 511 hold a clean single marker and
79 hold the broken pattern.

`Techno1-1.wav` matched because that experiment never touched it.

## Decision

**Write both hot cues and beatgrids.** Both are validated end to end, in Serato,
on real data.

Still deliberately unwritten: `Autotags`, `Overview`, `Analysis`, `Offsets_`, and
`Markers_`. Nothing in Rekordbox maps to them.

## Consequences

**Positive**

- Hot cues and beatgrids survive the crossing, so a synced stick is usable in
  Serato without re-analysing.
- Cue colour needs no mapping table: Rekordbox stores RGB in the ANLZ entry, and
  Serato displayed those colours unchanged.
- 93% of the library is constant tempo, so almost every grid is a single marker.

**Negative / carried forward**

- **The variable-tempo path is untested.** 33 of 500 sampled tracks change
  tempo, the worst carrying 82 distinct values. Multi-marker grids are encoded
  but nothing has confirmed Serato reads them correctly, and that is where
  ADR 0006 went wrong.
- **Only WAV has been written.** The fixtures and this validation are WAV. 36 of
  40 sampled MP3s are ID3v2.3, which sizes frames differently from the v2.4 the
  writer was proven against; the MP3 path must be validated separately before
  use.
- **79 files hold a broken beatgrid** that this tool can now repair, but that
  repair has not been run.
