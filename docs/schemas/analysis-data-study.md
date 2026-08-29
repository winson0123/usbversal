# Analysis data: what Rekordbox holds and what Serato needs

Study of the full analysis surface — hot cues, beatgrid, BPM, key, gain —
derived from the `Techno1.BEFORE/AFTER.wav` fixture pair and from real data on
the `/mnt/usb` stick (2026-08-21).

Status tags follow [serato-schema-notes.md](serato-schema-notes.md):
`[verified]` from the byte-exact fixture pair, `[confirmed]` on the real stick.

---

## What a Lexicon sync actually changed [verified]

Whole-file diff of the fixture pair, chunk by chunk:

| RIFF chunk | Before | After | Changed |
|------------|--------|-------|---------|
| `fmt ` | 16 B | 16 B | no |
| `data` (audio) | 467,106 B | 467,106 B | **no** |
| `DISP` / `iXML` / `_PMX` / `LIST` | — | — | no |
| `id3 ` | 1,910 B | 1,901 B | **yes** |

**The audio is untouched.** Only the ID3 chunk is rewritten, and it came out
9 bytes *smaller* despite gaining two cues.

Frame by frame:

| Frame | Before | After | Note |
|-------|--------|-------|------|
| `Serato Markers2` | 470 B | 470 B | **content changed** — two `CUE` entries added |
| `Serato BeatGrid` | 15 B | 15 B | **byte-identical** |
| `Serato Autotags` | 21 B | 21 B | **byte-identical** |
| `TIT2` `TPE1` `TALB` `TCON` `TKEY` `TBPM` `COMM` `TRCK` | — | 1–2 B smaller each | trailing NUL dropped |
| `POPM` | 6 B | 6 B | unchanged |
| padding | 1024 B | 1024 B | unchanged |

The size shrink is entirely the dropped NUL terminators on text frames; both
forms are valid ID3. **Lexicon wrote no beatgrid and no autotags.** Note the
fixture already carried both before the sync, so this shows Lexicon leaves them
alone, not that it would decline to create them.

---

## The five pieces of analysis data

### 1. Hot cues — `PCO2` → `Serato Markers2` [verified both ends]

| | Rekordbox | Serato |
|---|---|---|
| Location | `ANLZ*.EXT`, `PCO2` where list type = 1 | `Serato Markers2` GEOB |
| Numbering | hot cue 1-based | slot 0-based (`hot_cue - 1`) |
| Position | u32 BE milliseconds | u32 BE milliseconds — same unit |
| Colour | RGB at PCP2 body offset 28 | 3 bytes at CUE body offset 7 |

Verified on `Techno1-1.wav`: Rekordbox holds cue 1 @ 0 ms and cue 2 @ 441 ms;
Lexicon wrote slot 0 @ 0 ms and slot 1 @ 441 ms. Same cues, same positions.

Memory cues (list type 0) occupy no Serato slot and are ignored.

**Colour lives at offset 28, not the last 3 bytes.** A real Rekordbox 6/7
`.EXT` PCP2 body is 72 bytes: RGB, then a comment. The trailing bytes are
NULs, so reading `body[-3:]` wrote `#000000` into every Serato cue
(TASK-253, confirmed on WONSIN). Lexicon also mapped `#FF0017` → `#CC0044`
and `#00C4FF` → `#0088CC` onto a Serato palette; we write the Rekordbox RGB
as-is (ADR 0008: Serato displayed those values on Pocket).

### 2. Beatgrid — `PQTZ` → `Serato BeatGrid` [format verified, mapping inferred]

Rekordbox `PQTZ` holds one entry per beat: `u2 beat_number` (1–4),
`u2 tempo` (BPM × 100), `u4 time` (ms).

`Techno1-1.wav`: 5 beats, all 136.00 BPM, at 0 / 441 / 882 / 1324 / 1765 ms.
Beat spacing 441 ms = 60000 / 136 — constant tempo.

Serato's `BeatGrid` for the same track is a single terminal marker,
`pos=0.0s bpm=136.0`:

```text
01 00 | 00000001 | 00000000 43080000 | 00
   ^      ^          ^        ^         ^
 version  markers    pos=0.0  bpm=136   trailing
```

So for constant tempo the mapping is trivial: one terminal marker at the first
beat's time, carrying the tempo. Variable tempo needs the non-terminal form,
`(position_sec, beats_to_next_marker)` per tempo change, then a terminal.

**93% of the library is constant tempo** [confirmed]: of 500 tracks sampled,
460 constant, 33 variable, 7 with no `PQTZ`. The worst variable track carries
82 distinct tempo values.

### 3. BPM — three places agree [verified]

| Where | Value |
|-------|-------|
| Rekordbox `bpmx100` | 13600 → 136.0 |
| `Serato BeatGrid` terminal | 136.0 |
| `Serato Autotags` field 1 | `136.00` |
| ID3 `TBPM` | `136` |

One source, three representations: float in the beatgrid, 2dp string in
Autotags, integer string in `TBPM`.

### 4. Key — passes through unchanged [verified]

Rekordbox `key_id` 29 resolves to `4A`; ID3 `TKEY` is `4A`. An exact match, and
Rekordbox is already storing Camelot here.

Note this differs from `database V2`'s `tkey`, where 35 of 46 Rekordbox keys map
to more than one Serato value — that field was not derived from Rekordbox. The
ID3 `TKEY` correspondence is direct.

### 5. Gain — `Serato Autotags` [verified, no Rekordbox source]

```text
01 01 | "136.00"\0 "0.000"\0 "0.000"\0
         bpm        autogain   gaindb
```

Rekordbox exposes no autogain equivalent, so there is nothing to map. Leave the
frame alone where it exists.

---

## What the write path faces [confirmed]

Sampling 40 library MP3s:

| Property | Finding |
|----------|---------|
| ID3 present | 40 / 40 |
| **ID3 version** | **36 are v2.3, 4 are v2.4** |
| `Serato Markers2` already present | 29 / 40 |
| `Serato Markers_` (v1) already present | 29 / 40 |
| Full analysis set (BeatGrid, Autotags, Analysis, Overview, Offsets_) | 10 / 40 |

Two consequences:

1. **The mixed ID3 version is a hazard.** v2.3 stores frame sizes as a plain
   u32; v2.4 uses synchsafe integers. The fixtures are v2.4, so the only
   container with ground truth is the *less* common one in the library. A
   writer that assumes v2.4 will corrupt v2.3 tags.
2. **Most files are updates, not creations.** `Serato Markers2` already exists
   on 29 of 40, so the writer must preserve the entries it does not own —
   `COLOR`, `BPMLOCK`, and on these files also `Serato Markers_`, the older cue
   format that may need to stay consistent.

---

## Recommended scope

> **Corrected 2026-08-21.** This section originally advised against writing
> beatgrids on the grounds that Lexicon never writes them, so nothing could
> validate the output. That was the wrong oracle to look for: Rekordbox's own
> `PQTZ` reproduces the existing frame byte for byte, and Serato accepted both
> cues and grids on the stick. See [ADR 0008](../decisions/0008-beatgrid-and-cue-sync-validated-in-serato.md).

Write **`Serato Markers2` and `Serato BeatGrid`**. Specifically:

- **Do** write hot cues. Reproducing the fixture diff is a byte-exact test.
- **Do** write beatgrids. Generating from `PQTZ` reproduces the existing frame
  exactly, and Serato renders the result correctly.
- **Do not** touch `Autotags`, `Overview`, `Analysis`, `Offsets_`, or
  `Markers_`. Nothing maps to them and Lexicon leaves them alone.
- **Do not** rewrite text frames. Lexicon's NUL-stripping is incidental; BPM and
  key already agree with Rekordbox.

## Open before writing

1. ~~Audio files are not in the backup set.~~ Resolved: the `test` playlist run
   backed up all four WAVs alongside both libraries, verified by checksum.
2. The MP3 path has no fixture. v2.3 in particular is untested.
3. Colour policy: pass Rekordbox RGB through, or map onto Serato's palette as
   Lexicon does. Nearly moot at 230/232 uncoloured.
4. Whether `Serato Markers_` (v1) must stay consistent with `Markers2` on the
   29/40 files carrying both.

---

## Variable-tempo beatgrids [confirmed]

Research, 2026-08-21, against 200 tracks on the stick.

### A bug the validated case could not catch

`beats_to_next` is the **index delta between markers**, not the length of the
tempo run. The first implementation used the run length, which understates the
count by one and makes Serato derive a slower tempo for the segment: four beats
over two seconds encoded as three, implying 90 BPM instead of 120.

Constant-tempo tracks are a single terminal marker and carry no `beats_to_next`
at all, so the validated case could never have exposed this. **Every
variable-tempo grid would have been wrong.**

### Why Rekordbox's tempo cannot be trusted as a grouping key

Rekordbox reports a smoothed tempo while the beat times themselves jitter. On a
live-recorded track, gaps run 450–470 ms while the declared tempo sits at
129.91 throughout:

```text
beat  1: gap=460ms declared=129.91 implied=130.43
beat  2: gap=470ms declared=129.91 implied=127.66
beat  3: gap=450ms declared=129.91 implied=133.33
```

Grouping by declared tempo assumes even spacing inside the run, so error
accumulates — up to 175 ms over 386 beats, half a beat at that tempo.

Markers are therefore closed when interpolated beats drift beyond a threshold,
not only when the tempo changes, and a tempo change splits at exactly the beat
that changed.

### Accuracy reached

Beat positions reconstructed from the encoded grid, against Rekordbox's:

| | tracks | worst error |
|---|---|---|
| Constant tempo | 188 | **10.9 ms** |
| Variable tempo | 12 | 115.0 ms (median 32.8 ms) |

### The floor that tuning cannot reach

Lowering the drift threshold from 10 ms to 0.5 ms improves the worst case to
about 50 ms and then stops, while payloads grow from 15 bytes to roughly 5 KB.

The residue is structural. A terminal marker means *this tempo holds to the end
of the track*, so any wander after the final section start is unrepresentable.
Making the terminal the last beat would fix it and would also stop a steady
track encoding as the single marker Serato was verified to accept.

### Recommendation

> **Corrected 2026-08-26.** This section previously advised syncing beatgrids
> for constant-tempo tracks only, on the grounds that a single marker cannot
> represent a ramp and 100 ms of drift is audible. Both halves were wrong.
> Serato writes a single marker for variable-tempo tracks too — of 60 untouched
> tracks carrying both a Serato grid and Rekordbox beats, every one has exactly
> one marker, including two the analysis reports as variable. And the drift
> came from anchoring on every per-bar tempo reading, which is mostly jitter.

Sync beatgrids for **every track**. Open a marker only where the tempo has moved
more than 2 BPM from the last anchor. That collapses the three cases into one
rule:

| Track | Markers |
|-------|---------|
| Steady tempo | 1 — the 14-byte terminal marker Serato writes itself |
| Two-section transition | 2 |
| Ramped transition | ~4 |

Rekordbox measures tempo once per bar and those readings wobble ±0.1 BPM, so
counting distinct tempos badly overstates movement: `Apt X Blue` reports 28
distinct tempos across 93 runs, but is steady at 149 until 84 s, ramps for about
seven seconds, then holds 140 — exactly its title of 149→140.
