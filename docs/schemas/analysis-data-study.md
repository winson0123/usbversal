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
| Colour | RGB in the entry's last 3 bytes | 3 bytes at body offset 7 |

Verified on `Techno1-1.wav`: Rekordbox holds cue 1 @ 0 ms and cue 2 @ 441 ms;
Lexicon wrote slot 0 @ 0 ms and slot 1 @ 441 ms. Same cues, same positions.

Memory cues (list type 0) occupy no Serato slot and are ignored.

**Colour is not carried across unchanged.** Rekordbox records `#FF0017` and
`#00C4FF`; Lexicon wrote `#CC0044` and `#0088CC`, so it maps onto a Serato
palette. This matters little in practice: of 232 hot cues across 400 tracks,
**230 have no colour at all** (`#000000`).

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

Write **`Serato Markers2` only**, matching the one behaviour with a verified
oracle. Specifically:

- **Do** write hot cues. Reproducing the fixture diff is a byte-exact test.
- **Do not** write `Serato BeatGrid` — the format is decoded, and constant-tempo
  mapping is straightforward, but Lexicon never writes it, so there is no
  reference for what Serato accepts. It is also where the earlier attempt
  produced a 2 BPM first bar ([ADR 0006](../decisions/0006-serato-analyzed-and-beatgrid-tags.md)).
- **Do not** touch `Autotags`, `Overview`, `Analysis`, `Offsets_`, or
  `Markers_`. Nothing maps to them and Lexicon leaves them alone.
- **Do not** rewrite text frames. Lexicon's NUL-stripping is incidental; BPM and
  key already agree with Rekordbox.

## Open before writing

1. Audio files are **not in the backup set**. This is the blocker.
2. The MP3 path has no fixture. v2.3 in particular is untested.
3. Colour policy: pass Rekordbox RGB through, or map onto Serato's palette as
   Lexicon does. Nearly moot at 230/232 uncoloured.
4. Whether `Serato Markers_` (v1) must stay consistent with `Markers2` on the
   29/40 files carrying both.
