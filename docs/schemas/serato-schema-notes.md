# Serato Schema Notes

Accumulated reverse-engineering and tooling notes.

## Status legend

| Tag | Meaning |
|-----|---------|
| [verified] | Decoded from a byte-exact before/after fixture; reproducible in tests |
| [confirmed] | Verified on test USB or with serato-tools |
| [assumed] | Not verified on disk |
| [unknown] | Needs research |

`[verified]` entries come from a controlled Lexicon experiment (2026-08-21):
baseline → rekordbox import → Lexicon export to Serato, diffing every file
byte-for-byte at each step, cross-checked against Lexicon's own database values.
Ground-truth pair retained at [`tests/fixtures/serato/`](../../tests/fixtures/serato/).

---

## Library root [confirmed]

```text
/mnt/usb/_Serato_/
  database V2            # library index
  neworder.pref          # crate display order
  Metadata/              # empty on test USB export
  Subcrates/
    Contents.crate
    Serato Stems/        # optional stems crate dir
```

A rekordbox-exported stick that has *also* been touched by Serato/Lexicon may
carry `_Serato_Backup/` and `_Serato_/Lexicon/` (its own backup zips) as well.

**Serato and rekordbox occupy disjoint directories** — `PIONEER/` is rekordbox's,
`_Serato_/` is Serato's, `Contents/` holds the audio both index. A second index
can be written over the same audio without duplicating or moving anything.

---

## TLV container format [verified]

`database V2`, `*.crate`, and `*.smartcrate` are the **same** flat TLV stream
with no header:

```text
repeat: [ 4-byte ASCII tag ][ 4-byte big-endian length ][ payload ]
```

Value type is determined by the **first character of the tag**:

| Prefix | Type |
|--------|------|
| `v`, `t`, `p` | UTF-16**BE** string |
| `u` | u32 big-endian |
| `s` | u16 big-endian |
| `b` | u8 (boolean) |
| `o` | container — payload is a nested TLV stream |

There is no length prefix on strings beyond the TLV length itself, and no
NUL terminator.

---

## Path convention [verified]

`ptrk` (crate) and `pfil` (database V2) are **drive-relative, with no drive
letter and no leading slash**, forward slashes throughout:

| Source | Stored as |
|--------|-----------|
| `C:\Users\Winson\Music\...\Techno1.wav` | `Users/Winson/Music/.../Techno1.wav` |
| `D:\Contents\Artist\Album\track.mp3` | `Contents/Artist/Album/track.mp3` |
| Rekordbox `content.path` = `/Contents/.../track.mp3` | `Contents/.../track.mp3` |

For a USB stick, paths are relative to the drive root, so a rekordbox
`content.path` converts by **stripping the single leading `/`** — no other
transformation. This is why the two vendors align on the same stick.

`app/core/track_paths.py:normalize_track_path` additionally lowercases; that is
a **match key only** and must never be written to disk.

---

## Crate files (`.crate`) [verified]

`_Serato_/Subcrates/<name>.crate`. Verified structure, in this exact order:

```text
vrsn = "1.0/Serato ScratchLive Crate"        UTF-16BE
osrt { tvcn="#", brev=0x00 }                 sort column
ovct { tvcn="genre",   tvcw="0" }            column definitions,
ovct { tvcn="song",    tvcw="0" }            one per visible column
ovct { tvcn="key",     tvcw="0" }
ovct { tvcn="bpm",     tvcw="0" }
ovct { tvcn="bitrate", tvcw="0" }
ovct { tvcn="length",  tvcw="0" }
otrk { ptrk="Users/Winson/Music/.../Techno1.wav" }    one per track,
otrk { ptrk=... }                                     IN PLAYLIST ORDER
```

**Playlist order is carried by `otrk` sequence.** Verified: the four `otrk`
entries matched Lexicon's `LinkTrackPlaylist.position` 0..3 exactly.

The `ovct` column set is **cosmetic** (display columns). Crates written by
usbversal via `serato-tools` use a different column set
(`song`/`playCount`/`artist`/`bpm`/`key`/`album`/`length`/`comment`/`added`)
and are structurally valid.

### Nested playlist folders [confirmed — Serato, 2026-08-27]

Serato's crate list is flat. Hierarchy is encoded in the filename with `%%`
as separator:

```text
rekordbox  Gigs / Played / safety day   ->   Subcrates/Gigs%%Played%%safety day.crate
```

`crate_name_for()` walks each ancestor folder, then the playlist, joined with
`%%`. Confirmed in Serato after syncing Rekordbox `Gigs → Played → safety day`
(TASK-245/246): the crate appears under Played under Gigs. No empty parent
crate files are required — `Gigs%%Played%%safety day.crate` alone is enough.

TASK-255 prefixes the thumbdrive label as the outermost parent:
`WONSIN%%Gigs%%Played%%safety day.crate`. See [volume-crate.md](../workflows/volume-crate.md).

---

## `location.sqlite` — the library Serato actually reads [confirmed]

`_Serato_/Library/location.sqlite`. **`database V2` is legacy.** This SQLite
database is what Serato reads for its library list, and it tracks the old file
explicitly: `last_seen_dbv2_library` holds `database V2`'s name, size and MD5,
and `dbv2_status` records import and export revisions. Serato imports the flat
file, then works from here.

The split that matters:

| Shown | Read from |
|-------|-----------|
| Beatgrid, hot cues, deck BPM | the audio file's GEOB frames |
| Library list BPM and key | `location.sqlite` |

So a track can load on the deck with a correct Rekordbox grid while the list
still shows Serato's own BPM. Both are right; they are different sources.

### The `asset` table

One row per track, 797 on the test stick. Columns that matter:

| Column | Meaning |
|--------|---------|
| `portable_id` | drive-relative path, matching the `pfil` form |
| `bpm`, `key` | what the library list displays |
| `revision` | per-row counter; `space.revision` follows the maximum |
| `is_stale` | set when Serato should re-read the file |
| `analysis_flags` | bitmap; 31 on analysed tracks |
| `file_size`, `time_modified` | how Serato decides a file changed |
| `type_specific_data` | **empty** — the beatgrid is not stored here |

Global counters live in `serato.revision` and `master.revision`, both above the
per-row maximum. There are no triggers on `asset`.

### Why our writes go unnoticed

Tag writes are size-preserving, because moving the audio stream invalidates
`Serato Offsets_` and the waveform preview renders wrong. But that means
`asset.file_size` never changes, `is_stale` stays 0, and Serato never re-reads
the file. **Updating this index is required, not cosmetic.**

`app/adapters/serato/library_db.py` reads and updates it: changed rows take new
revisions above the current maximum, `space.revision` follows, and rows are
marked stale. Rows Serato does not know are skipped rather than inserted.

The revision semantics are inferred from observing the schema, not documented.
Back the file up before writing to it.

## `database V2` [verified]

`_Serato_/database V2`:

```text
vrsn = "2.0/Serato Scratch LIVE Database"
otrk { ...fields... }    one per track
```

Verified fields from a real `otrk` (WAV example):

| Tag | Type | Example | Meaning |
|-----|------|---------|---------|
| `ttyp` | str | `wave` | file type — `mp3` for a rekordbox USB |
| `pfil` | str | `Users/.../House1.wav` | drive-relative path |
| `tsng` | str | `House 1` | title |
| `tart` | str | `rekordbox` | artist |
| `talb` | str | `GROOVE CIRCUIT FACTORY SAMPLES` | album |
| `tgen` | str | `Loop Samples` | genre |
| `tlen` | str | `00:01.0` | duration, formatted |
| `tsiz` | str | `0.5MB` | size, formatted |
| `tbit` | str | `2116.0kbps` | bitrate |
| `tbpm` | str | `123.00` | **BPM as a string, 2dp** |
| `tkey` | str | `8A` | key |
| `tcom` | str | `4-Floor / Breaks Kit (A-1)` | comment |
| `tadd` | str | `1767801600` | date added, epoch as string |
| `uadd` | u32 | `1767801600` | date added, epoch |
| `ufsb` | u32 | `523592` | file size in bytes |
| `ulbl` | u32 | `16777215` | label colour (0xFFFFFF) |
| `bply` | u8 | `0` | played |
| `bbgl` | u8 | `1` | beatgrid locked |
| `bovc` | u8 | `1` | overview computed |
| `tgrp` `trmx` `tlbl` `tcmp` `ttyr` | str | empty | grouping / remixer / label / composer / year |
| `utkn` | u32 | `0` | track number |

The record above is **complete and working** — every field Serato needs for a
usable library entry. Richer records seen on MP3/MP4 entries may additionally
carry `tsmp`, `utme`, `utpc`, `sbav`, `bhrt`, `bmis`, `blop`, `bitu`, `bcrt`,
`biro`, `bwlb`, `bwll`, `buns`, `bkrk`. These are **not required**.

### Real-stick field distribution [confirmed — `/mnt/usb`, 2026-08-21]

Decoded directly from `/mnt/usb/_Serato_/database V2` (522,473 bytes,
`2.0/Serato Scratch LIVE Database`, **793 `otrk`**, all MP3). This corrects an
impression the WAV fixture alone would give:

**Fields are sparse and optional — there is no fixed record shape.** Frequency
across all 793 records:

| Field | Present | Field | Present |
|-------|---------|-------|---------|
| `ttyp` `pfil` `tsng` `tbpm` `tadd` `uadd` `utme` `utpc` `sbav` | 793 (all) | `tart` | 774 |
| all `b*` flags (`bhrt` `bmis` `bply` `blop` `bitu` `bovc` `bcrt` `biro` `bwlb` `bwll` `buns` `bbgl` `bkrk`) | 793 (all) | `ulbl` | 747 |
| `ttyr` | 726 | `tgen` | 710 |
| `tkey` | 670 | `talb` | 299 |
| `tcom` | 277 | `tsiz` `ufsb` | 211 |
| `tlen` | 183 | `tbit` `tsmp` | 182 |
| `utkn` | 97 | `tcmp` | 88 |
| `tlbl` | 65 | `tgrp` | 39 |
| `udsc` | 24 | `trmx` | 16 |

Consequences for a writer:

- **Never assume a field is present** when reading; never pad absent fields with
  empty values when updating an existing record.
- `tlen` / `tsiz` / `tbit` / `tsmp` / `ufsb` are missing from ~75% of real
  records, so they are **not required** — consistent with the WAV fixture being
  a complete-but-not-minimal example.
- **`udsc`** (disc number, u32) appears here and is **absent from the fixture's
  field list** — evidence that the tag vocabulary is open. Preserve unknown tags
  verbatim.
- `ttyp` is `mp3` on this stick, confirming the value for a rekordbox USB.
- `pfil` is `Contents/Alice Deejay/.../track.mp3` — drive-relative, no leading
  slash, exactly as specified.

### Crate and `neworder.pref` on the real stick [confirmed]

`Subcrates/Pocket.crate` (14,561 bytes): `vrsn` = `1.0/Serato ScratchLive Crate`,
`osrt` = `{tvcn: "key", brev: 0}`, **9 `ovct`** columns
(`song`, `playCount`, `artist`, `bpm`, `key`, `album`, `length`, …), then
**80 `otrk`**. The `osrt`/`ovct` set differs from the Lexicon fixture's
(`#` sort, 6 columns) — confirming these are **display preferences, not
structure**. usbversal's `serato-tools`-written crates use this same 9-column
set, so its output is consistent with what already ships on the stick.

`neworder.pref` (84 bytes) decodes to exactly:

```text
[begin record]
[crate]Pocket
[end record]
```

**This file exists on the live stick and is not in usbversal's backup set** —
a rollback today would not restore it. See TASK-071.

The stick also carries `DBV2-legacy.zip`, `Export Backups/`, `Library/`, and
`Lexicon/` beside `_Serato_`'s own files; a backup routine should not assume the
directory contains only `database V2` and `Subcrates/`.

### Merge, do not clobber [confirmed]

A rekordbox stick that has seen Lexicon or Serato **already has a real
`database V2`** (522 KB / 793 tracks on the `/mnt/usb` test stick). Any writer
must read existing `otrk` records, key them by `pfil`, then add or update — never
regenerate. Unrecognized tags inside an existing `otrk` must be preserved
verbatim (`unknown_field_preservation`).

`serato_tools.usb_export.copy_crates_to_usb` **`shutil.rmtree`s the destination
`_Serato_` directory** (its own source carries a `TODO: merge with existing,
instead of replacing`). Do not use it.

---

## `neworder.pref` [verified]

`_Serato_/neworder.pref` — UTF-16**BE** plain text, crate display order. The
80-byte single-crate example decodes to exactly:

```text
[begin record]
[crate]test
[end record]
```

(trailing newline present). One `[crate]<name>` line per crate, in display order.

Lexicon **rewrites this on every sync**. usbversal currently neither writes it
nor backs it up — see TASK-071/TASK-074.

---

## Hot cues — `Serato Markers2` GEOB [verified]

ID3v2.4 `GEOB` frame, description `Serato Markers2`.

Payload wrapper:

```text
[0x01][0x01][ base64 ASCII, may contain \n and trailing NULs ]
```

Strip `\r`, `\n`, `\x00`. If the remaining alphabet length is `4n+1`, drop
the last character — that leftover cannot encode a byte and is not a
truncated field (see [ADR 0010](../decisions/0010-tolerate-leftover-markers2-base64.md)).
Re-pad to a multiple of 4, base64-decode. Do not cut at 64 characters;
that would truncate `BPMLOCK`. The decoded blob is:

```text
[0x01][0x01] then repeated entries:
  [ name, NUL-terminated ASCII ][ u32 BE length ][ body ]
then a single trailing 0x00
```

Entry types observed: `COLOR`, `BPMLOCK`, `CUE`. Documented elsewhere but not
observed here: `LOOP`, `FLIP`.

`CUE` body — 13 bytes plus name:

| Offset | Size | Meaning |
|--------|------|---------|
| 0 | 1 | `0x00` |
| 1 | 1 | **cue slot index** (0-based) |
| 2 | 4 | **position, u32 BE, MILLISECONDS** |
| 6 | 1 | `0x00` |
| 7 | 3 | RGB colour |
| 10 | 2 | `0x00 0x00` |
| 12 | .. | cue name, NUL-terminated (empty in the sample) |

`COLOR` body: `00 FF FF FF`. `BPMLOCK` body: `01`.

Verified end-to-end against Lexicon's own database:

| Lexicon `Cuepoint` | Serato `CUE` |
|--------------------|--------------|
| `startTime 0.0`, `position 0`, `magenta_red` | `slot=0 pos=0ms color=#CC0044` |
| `startTime 0.441`, `position 1`, `blue_light` | `slot=1 pos=441ms color=#0088CC` |

So **seconds × 1000 → u32 BE**, and rekordbox cue `position` → Serato slot index.

### Ground-truth blobs

Decoded `Serato Markers2` payload, `Techno1.BEFORE.wav` (30 bytes):

```text
0101 434f4c4f5200 00000004 00ffffff
     42504d4c4f434b00 00000001 01
     00
```

`Techno1.AFTER.wav` (72 bytes) — same, plus two `CUE` entries:

```text
0101 434f4c4f5200 00000004 00ffffff
     42504d4c4f434b00 00000001 01
     43554500 0000000d 00 00 00000000 00 cc0044 0000 00
     43554500 0000000d 00 01 000001b9 00 0088cc 0000 00
     00
```

`0x1b9` = 441 ms. A writer is correct when applying AFTER's cue list to BEFORE
reproduces the AFTER payload byte-for-byte.

### Cue colour mapping [unknown]

**Only two of N mappings are known**: `magenta_red` → `#CC0044`,
`blue_light` → `#0088CC`. The rest of the rekordbox → Serato colour table must
be derived from rekordbox's cue colour IDs, or by running more samples through
Lexicon. See TASK-081.

---

## Beatgrid — `Serato BeatGrid` GEOB [verified format, not written by Lexicon]

```text
[0x01][0x00][ u32 BE marker_count ]
  (marker_count - 1) x non-terminal: [ float32 BE position_sec ][ u32 BE beats_to_next_marker ]
  1 x terminal:                      [ float32 BE position_sec ][ float32 BE bpm ]
[ 1 trailing byte, 0x00 ]
```

Ground truth, both fixtures (15 bytes, identical before and after):

```text
01 00 00000001 00000000 43080000 00
```

`marker_count=1`, terminal `pos=0.0s`, `bpm=136.000` (`0x43080000`), trailing
`0x00`. This matched rekordbox's BPM of 136.0.

**Lexicon does not write beatgrids** — `Serato BeatGrid` and `Serato Autotags`
were byte-identical before and after on all four experiment files. Only
`Serato Markers2` changed, and only on the two tracks that had cues. There is no
Lexicon behaviour to copy here; beatgrids must be authored from rekordbox ANLZ
`PQTZ` data. Only **single-marker** grids were observed — the non-terminal
marker path for variable-tempo tracks is untested.

See [ADR 0006](../decisions/0006-serato-analyzed-and-beatgrid-tags.md) for the
earlier sparse-beatgrid failure and [ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md)
for why this is being revisited.

---

## `Serato Autotags` GEOB [verified]

`[0x01][0x01]` then three NUL-terminated ASCII strings — bpm, autogain, gaindb:

```text
0101 "136.00"\0 "0.000"\0 "0.000"\0
```

---

## Tag container: MP3, WAV, FLAC

| Container | Where the Serato payload lives |
|-----------|-------------------------------|
| **MP3** | ID3v2 GEOB at the head of the file. Frame sizes are synchsafe on v2.4, raw 32-bit on v2.3. |
| **WAV** | The ID3 stream is wrapped in a RIFF chunk with id `id3 `. The chunk must be rewritten **and the RIFF size field fixed**. |
| **FLAC** | Vorbis comments `SERATO_BEATGRID` / `SERATO_MARKERS_V2`. Value is base64 (no padding, newline every 72 characters) of `application/octet-stream\\0\\0` + description + payload. |

Chunk order observed in the WAV fixtures: `fmt ` / `data` / `DISP` / `iXML` / `_PMX` / `LIST` / `id3 `.

The Serato **marker payloads are identical across containers** — only the
wrapper differs. MP4 atoms are out of scope.

ID3 writes are size-preserving. FLAC comment blocks may grow; STREAMINFO and
the audio frames stay byte-identical.

---

## Parser status

| Component | Status |
|-----------|--------|
| `DatabaseV2` read | [confirmed] serato-tools |
| `Crate` read | [confirmed] serato-tools |
| `Crate` write | [confirmed] serato-tools `add_track` + `save`, structurally valid TLV |
| `database V2` append | [confirmed] via `DatabaseV2.entries` + the private `_dump()`; `save()` writes `raw_data`, which only `_dump()` refreshes, so appending to `entries` alone is silently discarded |
| `neworder.pref` read/write | not implemented |
| GEOB tag read/write | not implemented — `serato_tools` ships `track_cues_v2`, `track_beatgrid`, `track_autotags` (unevaluated) |

## Mutation safety

| Rule | Status |
|------|--------|
| Back up `_Serato_` before any byte write | required (TASK-011) |
| Backup set must include `neworder.pref` | **gap** — see TASK-071 |
| Merge existing records, never regenerate | required |
| Preserve unrecognized TLV tags verbatim | required |
| Serato must not be running during a write | operator precondition |

## Related

- [../planning/rekordbox-to-serato-playlist-migration.md](../planning/rekordbox-to-serato-playlist-migration.md)
- [../planning/rekordbox-to-serato-analysis-sync.md](../planning/rekordbox-to-serato-analysis-sync.md)
- [../adapters/serato.md](../adapters/serato.md)
