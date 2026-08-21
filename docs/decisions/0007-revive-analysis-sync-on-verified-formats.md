# ADR 0007: Revive Serato analysis sync on verified write formats

**Status:** accepted
**Date:** 2026-08-21
**Supersedes:** [ADR 0006](0006-serato-analyzed-and-beatgrid-tags.md)

## Context

ADR 0006 abandoned Rekordbox → Serato analysis tag sync. On an 80-track test
stick Serato reported **24 analyzed / 56 unanalyzed** even though all 79 MP3s
carried a full GEOB set. The observed correlation was that Serato's analyzed
count matched **`Serato Markers2` cue content**, not tag presence — tracks whose
Markers2 held only `COLOR` + `BPMLOCK` stayed unanalyzed. The team could not
explain *why*, and an attempted workaround (injecting a synthetic anchor cue
near the first beat) was undocumented and fragile. The work was removed.

A controlled experiment on 2026-08-21 changed the evidence base. Baseline →
rekordbox import into Lexicon → Lexicon export to Serato, with every file
diffed byte-for-byte at each step and cross-checked against Lexicon's own
database. Lexicon is a shipping commercial product whose Serato output Serato
accepts, so its behaviour is a **known-good reference** rather than a guess.

## What the experiment established

1. **Lexicon writes exactly four things** on a sync, all inside `_Serato_/`:
   `Subcrates/<playlist>.crate`, a rewritten `database V2`, a rewritten
   `neworder.pref`, and its own backup zip.

2. **Lexicon does not write beatgrids.** `Serato BeatGrid` and
   `Serato Autotags` were byte-identical before and after on all four files.
   Only `Serato Markers2` changed, and only on the two tracks that had cues.

3. **The `Serato Markers2` `CUE` layout is now decoded and verified** against
   Lexicon's `Cuepoint` rows: seconds × 1000 → u32 BE position, rekordbox cue
   `position` → Serato slot index, 3-byte RGB colour. See
   [serato-schema-notes.md](../schemas/serato-schema-notes.md).

4. **ADR 0006's correlation is explained, not contradicted.** Lexicon produces
   Serato-visible tracks by writing *real hot cues* into Markers2. ADR 0006's
   failure was not that cues are the wrong lever — it was that the cues being
   written were synthetic anchors rather than the track's actual rekordbox hot
   cues, sourced from ANLZ `PCO2`.

## Decision

**Revive analysis sync (TASK-034 lineage), sequenced behind index authoring.**

Specifically:

- Stage 1 (index) comes first and is independently useful: author
  `database V2` records and `neworder.pref` so a rekordbox-only stick becomes
  Serato-readable at all. This requires **no audio file mutation**.
- Stage 2 (analysis) writes `Serato Markers2` from ANLZ `PCO2` **hot cues** —
  real cues, not anchors — and `Serato BeatGrid` from `PQTZ`.
- Beatgrid authoring has **no reference implementation to copy**, since Lexicon
  declines to write them. It is therefore the lowest-confidence part of Stage 2
  and ships behind an explicit opt-in flag, separate from cue sync.

## Consequences

**Positive**

- The write formats are now specified from ground truth rather than inference,
  with a retained before/after fixture pair enabling byte-exact round-trip tests
  ([`tests/fixtures/serato/`](../../tests/fixtures/serato/)).
- Stage 1 delivers the project's actual mission — one stick readable by both
  ecosystems — without touching a single audio file.

**Negative / risks carried forward**

- **The cue colour table is 2 entries deep.** `magenta_red` → `#CC0044`,
  `blue_light` → `#0088CC`. The rest is unknown (TASK-081).
- **The MP3 container path is untested.** The experiment used WAV, where the ID3
  stream is wrapped in a RIFF `id3 ` chunk. A rekordbox USB is all MP3.
- **Only single-marker beatgrids were observed.** ADR 0006's sparse-grid maths
  bug (a 2 BPM first bar from a hard-coded +120 s terminal marker) remains a
  live hazard for variable-tempo tracks.
- **ANLZ and `export.pdb` have never been parsed.** Everything about the
  rekordbox read side of Stage 2 is from public documentation, not this data.
- Stage 2 still mutates the user's audio files and stays gated behind explicit
  confirmation plus a backup of every file it touches.

ADR 0006's measurements remain valid and are retained; only its *conclusion* is
superseded.
