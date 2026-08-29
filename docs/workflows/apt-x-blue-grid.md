# Apt X Blue variable-tempo grid

**File:** `Contents/Rosé, Bruno Mars & Gigi Dagosto/UnknownAlbum/Ros & Bruno Mars X Gigi Dagostino - Apt X Bl.mp3`

## Deck check (2026-08-29)

Serato loads the four-marker grid. The playhead follows the 149→140 ramp.
TASK-251 is confirmed.

The last marker showed **140.9**, not the intended **140**.

## Why 140.9

`_anchors` opens a marker when tempo moves more than 2 BPM. The last
anchor is therefore the **first** downbeat of the closing section, still
mid-ramp at 140.87. The section then holds 140. The terminal marker used
that first reading as its BPM, and Serato displays it.

On disk before the fix (byte-identical to the old encoder):

| Kind | Position (s) | Value |
|------|--------------|-------|
| step | 0.040 | 212 beats to next |
| step | 85.430 | 4 beats to next |
| step | 87.070 | 8 beats to next |
| terminal | 90.440 | 140.87 BPM |

Rekordbox first beat: 148.81 BPM at 40 ms. Title tempo is 149→140.

## Fix (TASK-257)

A multi-marker grid's terminal BPM is the **median** of downbeats from
the last anchor to the end. A single-marker (steady) grid still uses the
first downbeat's BPM.

Re-sync this track to rewrite the last marker as 140.
