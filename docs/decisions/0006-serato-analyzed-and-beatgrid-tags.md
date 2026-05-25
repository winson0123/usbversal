# ADR 0006: Serato “analyzed” gate and beatgrid encoding

**Status:** superseded (2026-05-25) — analysis tag sync abandoned; see [future work doc](../planning/rekordbox-to-serato-analysis-sync.md)  
**Date:** 2026-05-25

## Context

We attempted to copy Rekordbox BPM, key, beatgrid, and cues into Serato GEOB ID3 tags on USB-exported MP3s (`sync-analysis`). On a Pocket playlist test stick (80 tracks), Serato DJ showed **24 analyzed / 56 unanalyzed** even after writing Analysis, Overview, Autotags, BeatGrid, Markers2, and Markers_ on every MP3.

## Findings (retained for future work)

### 1. “Analyzed” is not “has Serato tags”

| Observation | Count |
|-------------|-------|
| MP3s with full GEOB set | 79/79 |
| MP3s Serato shows as analyzed | ~24 |
| MP3s with **≥1 CUE/LOOP** in `Serato Markers2` | 23 |
| MP3s with Markers2 **only COLOR + BPMLOCK** | 56 |

Serato’s analyzed count matched **Markers2 cue content**, not tag presence alone.

### 2. `Serato Offsets_` is not the analyzed gate

Nine MP3s had native `Serato Offsets_` (~16 KB). Fourteen analyzed MP3s had no Offsets_.

### 3. Sparse beatgrid math bug

Non-terminal marker at first beat with `beats_till_next_marker = 4` and terminal at **first beat + 120 s** yields segment BPM `4/120×60 = 2` for the first bar — matching user reports of 2 BPM and a bar jump at 2:00.

### 4. Dense beatgrid size was a red herring

Large grids were suspected to cause unanalyzed status; Markers2 without cues was the real gate.

## Decision (reversed)

~~Implement tag sync and anchor cues.~~ **Abandoned.** Usbversal will only migrate playlist membership; users run **Serato Analyze Files** after Rekordbox→Serato crate copy.

## Consequences

- Implementation removed: `sync-analysis` CLI, Rekordbox analysis reader, Serato GEOB writers.
- Findings preserved in this ADR and [rekordbox-to-serato-analysis-sync.md](../planning/rekordbox-to-serato-analysis-sync.md) for TASK-034 if revisited.
