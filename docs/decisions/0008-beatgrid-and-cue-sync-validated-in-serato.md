# ADR 0008: Write beatgrids and hot cues from Rekordbox ANLZ

**Status:** accepted
**Date:** 2026-08-21

## Context

A synced Serato stick is only usable if the deck sees the same grid and
cues the DJ set in Rekordbox. Rekordbox stores that data in ANLZ
(`PQTZ` beats, `PCP2` hot cues). Serato reads `Serato BeatGrid` and
`Serato Markers2` from the audio file.

## Decision

**Write both hot cues and beatgrids** from Rekordbox ANLZ onto the audio
file. Rekordbox beat data is the oracle: collapse runs of equal tempo
into BeatGrid markers, and copy cue time and RGB from PCP2.

Still deliberately unwritten: `Autotags`, `Overview`, `Analysis`,
`Offsets_`, and `Markers_`. Nothing in Rekordbox maps to them.

`location.sqlite` is updated on existing rows (`bpm`, `key`,
`analysis_flags = 24`) so the library list matches the file. The file
is never created or inserted into.

## Consequences

### Positive

- A synced stick is usable in Serato without re-analysing
- Cue colour needs no mapping table: Rekordbox stores RGB, and Serato
  displays it
- Most library tracks are constant tempo, so most grids are one marker

### Negative

- Variable-tempo grids follow multi-marker ANLZ; outliers are Rekordbox
  analysis, not the encoder
- Tag writes must stay size-preserving so `Serato Offsets_` stay valid
