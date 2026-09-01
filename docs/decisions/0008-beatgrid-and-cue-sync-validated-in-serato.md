# ADR 0008: Write beatgrids and hot cues from Rekordbox ANLZ

**Status:** accepted
**Date:** 2026-08-21

## Context

A synced stick is useless if the deck does not see the grid and cues
the DJ set in Rekordbox. Rekordbox keeps that in ANLZ (`PQTZ` beats,
`PCP2` hot cues). Serato reads `Serato BeatGrid` and `Serato Markers2`
from the audio file.

## Decision

Write both hot cues and beatgrids from Rekordbox ANLZ onto the audio
file. Rekordbox beat data is the source of truth. Collapse runs of
equal tempo into BeatGrid markers. Copy cue time and RGB from PCP2.

Still unwritten: `Autotags`, `Overview`, `Analysis`, `Offsets_`, and
`Markers_`. Nothing in Rekordbox maps to them.

`location.sqlite` is updated on existing rows (`bpm`, `key`,
`analysis_flags = 24`) so the library list matches the file. Usbversal
never creates that file or inserts into it.

## Consequences

You can play the stick in Serato without re-analysing. Cue colour
needs no mapping table. Rekordbox stores RGB and Serato shows it.
Most tracks are constant tempo, so most grids are one marker.

Variable-tempo grids follow multi-marker ANLZ. Odd grids are
Rekordbox analysis, not the usbversal encoder. Tag writes must keep the same
file size or `Serato Offsets_` go stale.
