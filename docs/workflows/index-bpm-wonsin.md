# `correct_index_bpm` live run — WONSIN, 2026-08-28

**Task:** TASK-250
**Mount:** `/media/crow/WONSIN`
**Backup:** `~/.local/share/usbversal/backups/WONSIN/20260828T072224Z`
**Wrote:** `_Serato_/Library/location.sqlite` only (no audio)

## Result

| | |
|---|---|
| Candidates (Rekordbox grid + existing index row) | 1286 |
| Rows written | 7 |
| Dry-run after write | 0 remaining |

The Contents sync had already corrected most index BPMs. The leftover
~70 half-tempo rows from the older test stick were not present here.

## The seven rows

Half / double tempo (the intended fix):

| Index BPM | First-beat BPM | Track |
|-----------|----------------|-------|
| 80.00 | 160.00 | Alicia Keys, Jay Z — Empire State of Mind (WAV) |
| 75.00 | 150.00 | Ellie Goulding — Lights (Club Mix) (AIF) |
| 80.00 | 160.00 | Keane — Somewhere Only We Know (AIF) |
| 75.00 | 150.00 | Kendrick Lamar — Humble. (MP3) |

Sub-0.02 float noise (exact `!=`, not a tempo error):

| Index BPM | First-beat BPM | Track |
|-----------|----------------|-------|
| 130.00 | 129.94 | David Guetta ft Kid Cudi — Memories |
| 104.99 | 105.00 | RJMrLA ft Ty Dolla Sign — Friday Night |
| 95.00 | 94.99 | Fetty Wap ft Remy Boyz — 679 |

## Decision

Keep the exact BPM inequality. A 0.01 difference is still a disagreement
with the first beat; rounding it away would hide real half-tempo cases
that land close after a bad analyse. The three float rows are cheap.

`correct_index_bpm` is still not in the TUI. This run was a one-shot
from the existing service function.
