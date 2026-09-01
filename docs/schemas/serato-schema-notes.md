# Serato schema notes

On-disk layouts the Serato adapter has to keep. I decoded the verified
rows from a Lexicon before/after pair on 2026-08-21, then checked them
on a real stick.

## Status legend

| Tag | Meaning |
|-----|---------|
| [verified] | Decoded from a byte-exact before/after fixture, reproducible in tests |
| [confirmed] | Checked on a test USB or with serato-tools |
| [assumed] | Not verified on disk |
| [unknown] | Needs research |

The [verified] rows come from that Lexicon run: baseline, rekordbox
import, Lexicon export to Serato, byte-for-byte diffs at each step,
checked against Lexicon's own database values. The pair is in
[`tests/fixtures/serato/`](../../tests/fixtures/serato/).

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

A rekordbox-exported stick that Serato or Lexicon has also touched may
carry `_Serato_Backup/` and `_Serato_/Lexicon/` next to those.

`PIONEER/` is rekordbox. `_Serato_/` is Serato. `Contents/` holds the
audio both index. A second index can sit on the same audio without
copying or moving a file.

## TLV container format [verified]

`database V2`, `*.crate`, and `*.smartcrate` are the same flat TLV
stream with no header:

```text
repeat: [ 4-byte ASCII tag ][ 4-byte big-endian length ][ payload ]
```

Value type is the first character of the tag:

| Prefix | Type |
|--------|------|
| `v`, `t`, `p` | UTF-16BE string |
| `u` | u32 big-endian |
| `s` | u16 big-endian |
| `b` | u8 (boolean) |
| `o` | container. Payload is a nested TLV stream |

There is no extra length prefix on strings, and no NUL terminator.

## Path convention [verified]

`ptrk` (crate) and `pfil` (database V2) are drive-relative. No drive
letter, no leading slash, forward slashes throughout:

| Source | Stored as |
|--------|-----------|
| `C:\Users\Winson\Music\...\Techno1.wav` | `Users/Winson/Music/.../Techno1.wav` |
| `D:\Contents\Artist\Album\track.mp3` | `Contents/Artist/Album/track.mp3` |
| Rekordbox `content.path` = `/Contents/.../track.mp3` | `Contents/.../track.mp3` |

On a USB stick, paths are relative to the drive root. Convert a
rekordbox `content.path` by stripping the single leading `/`. Nothing
else. That is why the two vendors line up on the same stick.

`app/core/track_paths.py:normalize_track_path` also lowercases. That
value is a match key only. Never write the lowercased form to disk.

## Crate files (`.crate`) [verified]

`_Serato_/Subcrates/<name>.crate`. Verified structure, in this exact
order:

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

Playlist order is the `otrk` sequence. The four `otrk` entries matched
Lexicon's `LinkTrackPlaylist.position` 0..3 exactly.

The `ovct` column set is cosmetic. Crates written by usbversal through
`serato-tools` use a different column set
(`song`/`playCount`/`artist`/`bpm`/`key`/`album`/`length`/`comment`/`added`)
and are still valid TLV.

### Nested playlist folders [confirmed, Serato, 2026-08-27]

Serato's crate list is flat. Hierarchy lives in the filename, `%%` as
separator:

```text
rekordbox  Gigs / Played / safety day   ->   Subcrates/Gigs%%Played%%safety day.crate
```

`crate_name_for()` walks each ancestor folder, then the playlist,
joined with `%%`. After syncing Rekordbox `Gigs → Played → safety day`,
the crate sat under Played under Gigs. Empty parent crate files are
not required. `Gigs%%Played%%safety day.crate` alone is enough. The
parent names (`Gigs`, `Gigs%%Played`) must still appear in
`neworder.pref`. A live WONSIN `neworder.pref` listed those folder
stems with no matching `.crate`. After a fresh export we only listed
the volume and the leaves, so Serato had nothing to hang
`WONSIN%%Gigs%%pocket …` on.

The thumbdrive label is the outermost parent:
`WONSIN%%Gigs%%Played%%safety day.crate`. An empty `WONSIN.crate` is
also written so Serato has a real folder node. See
[volume-crate.md](../workflows/volume-crate.md).

## `location.sqlite`, the library Serato actually reads [confirmed]

`_Serato_/Library/location.sqlite`. `database V2` is the old file.
This SQLite database is what Serato reads for its library list, and it
tracks the old file explicitly: `last_seen_dbv2_library` holds
`database V2`'s name, size and MD5, and `dbv2_status` records import
and export revisions. Serato imports the flat file, then works from
here.

The split that matters:

| Shown | Read from |
|-------|-----------|
| Beatgrid, hot cues, deck BPM | the audio file's GEOB frames |
| Library list BPM and key | `location.sqlite` |

A track can load on the deck with a correct Rekordbox grid while the
list still shows Serato's own BPM. Both are right. They are different
sources.

### The `asset` table

One row per track, 797 on the test stick. Columns that matter:

| Column | Meaning |
|--------|---------|
| `portable_id` | drive-relative path, matching the `pfil` form |
| `bpm`, `key` | what the library list displays |
| `revision` | per-row counter. `space.revision` follows the maximum |
| `is_stale` | set when Serato should re-read the file |
| `analysis_flags` | bitmap. Serato writes 24 after it analyses a track |
| `file_size`, `time_modified` | how Serato decides a file changed |
| `type_specific_data` | empty. The beatgrid is not stored here |

Global counters live in `serato.revision` and `master.revision`, both
above the per-row maximum. There are no triggers on `asset`.

### Why our writes go unnoticed

Tag writes keep the same file size, because moving the audio stream
invalidates `Serato Offsets_` and the waveform preview renders wrong.
That also means `asset.file_size` never changes, `is_stale` stays 0,
and Serato never re-reads the file. Updating this index is required.

`app/adapters/serato/library_db.py` reads and updates it. Changed rows
take new revisions above the current maximum, `space.revision`
follows, and rows are marked stale. Rows Serato does not know are
skipped rather than inserted.

The revision rules are inferred from the schema, not documented. Treat
the file as Serato-owned.

### Do not create or insert

Serato authors this file on first open by importing `database V2` and
reading tags. Bootstrap creates `_Serato_/`, `Subcrates/`, an empty
`database V2`, and `neworder.pref`. It does not create `Library/`.

WONSIN dump 2026-08-30 (360 KB, Serato-authored):

| Piece | What it is |
|-------|------------|
| Tables | 16: `asset`, `asset_auxiliary`, `container`, `container_asset`, `container_asset_list_columns`, `dbv2_status`, `dj_asset_metadata`, `dj_container_metadata`, `last_seen_dbv2_library`, `master`, `migration_script`, `serato`, `smart_crate_rules`, `space`, `space_asset`, `sqlite_sequence` |
| `asset` | 48 columns, one row per track |
| `space_asset` | required join, one row per asset |
| `container` / `container_asset` | crates |
| `migration_script` | 51 Serato-owned schema migrations |
| `master` / `serato` | UUID blob, sync secret, revision |
| `last_seen_dbv2_library` | `database V2` filename, size, MD5 |
| `dbv2_status` | import/export revisions and times |

Creating the file would invent that schema, the migrations, and the
import hashes. A wrong MD5 or `dbv2_status` can make Serato re-import
and overwrite list BPM, or refuse the library.

Insert is not needed after Serato creates the file. New tracks we
sync already get an `otrk` in `database V2`. Serato stores that
file's size and MD5 in `last_seen_dbv2_library` and creates `asset` /
`space_asset` rows on import. We only UPDATE `bpm`, `key`, and
`analysis_flags` on rows whose `portable_id` already exists, because
size-preserving tag writes do not make Serato re-read the file.
`analysis_flags` is set to 24, the value Serato writes after it
analyses a track, so the library list drops the unanalyzed count.
Rows that already have a non-zero flag are left alone. If the file
is absent, skip it. First-open list BPM comes from `database V2`
`tbpm` and the BeatGrid tag. The analysed mark is not available
until Serato has created this file.

## `database V2` [verified]

`_Serato_/database V2`:

```text
vrsn = "2.0/Serato Scratch LIVE Database"
otrk { ...fields... }    one per track
```

Verified fields from a real `otrk` (WAV example):

| Tag | Type | Example | Meaning |
|-----|------|---------|---------|
| `ttyp` | str | `wave` | file type. `mp3` for a rekordbox USB |
| `pfil` | str | `Users/.../House1.wav` | drive-relative path |
| `tsng` | str | `House 1` | title |
| `tart` | str | `rekordbox` | artist |
| `talb` | str | `GROOVE CIRCUIT FACTORY SAMPLES` | album |
| `tgen` | str | `Loop Samples` | genre |
| `tlen` | str | `00:01.0` | duration, formatted |
| `tsiz` | str | `0.5MB` | size, formatted |
| `tbit` | str | `2116.0kbps` | bitrate |
| `tbpm` | str | `123.00` | BPM as a string, 2dp |
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

That record is complete enough for Serato to show a usable library
entry. Richer MP3/MP4 records may also carry `tsmp`, `utme`, `utpc`,
`sbav`, `bhrt`, `bmis`, `blop`, `bitu`, `bcrt`, `biro`, `bwlb`,
`bwll`, `buns`, `bkrk`. Those are not required.

### Real-stick field distribution [confirmed, `/mnt/usb`, 2026-08-21]

Decoded directly from `/mnt/usb/_Serato_/database V2` (522,473 bytes,
`2.0/Serato Scratch LIVE Database`, 793 `otrk`, all MP3). The WAV
fixture alone would have lied about this.

Fields are sparse. There is no fixed record shape. Frequency across
all 793 records:

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

What that means for a writer:

- Never assume a field is present when reading. Never pad absent
  fields with empty values when updating an existing record.
- `tlen` / `tsiz` / `tbit` / `tsmp` / `ufsb` are missing from about
  75% of real records, so they are not required. The WAV fixture is a
  complete example, not a minimal one.
- `udsc` (disc number, u32) appears here and is absent from the
  fixture's field list. The tag vocabulary is open. Preserve unknown
  tags verbatim.
- `ttyp` is `mp3` on this stick, the value for a rekordbox USB.
- `pfil` is `Contents/Alice Deejay/.../track.mp3`. Drive-relative, no
  leading slash.

### Crate and `neworder.pref` on the real stick [confirmed]

`Subcrates/Pocket.crate` (14,561 bytes): `vrsn` = `1.0/Serato ScratchLive Crate`,
`osrt` = `{tvcn: "key", brev: 0}`, 9 `ovct` columns
(`song`, `playCount`, `artist`, `bpm`, `key`, `album`, `length`, …),
then 80 `otrk`. The `osrt`/`ovct` set differs from the Lexicon
fixture's (`#` sort, 6 columns). Those are display preferences, not
structure. usbversal's `serato-tools`-written crates use this same
9-column set.

`neworder.pref` (84 bytes) decodes to exactly:

```text
[begin record]
[crate]Pocket
[end record]
```

usbversal writes this file on every sync. Recovery of a wiped stick is
still restoring the Rekordbox USB.

The stick also carries `DBV2-legacy.zip`, `Export Backups/`,
`Library/`, and `Lexicon/` beside `_Serato_`'s own files. Do not assume
the directory holds only `database V2` and `Subcrates/`.

### Merge, do not clobber [confirmed]

A rekordbox stick that has seen Lexicon or Serato already has a real
`database V2` (522 KB / 793 tracks on the `/mnt/usb` test stick). Any
writer must read existing `otrk` records, key them by `pfil`, then add
or update. Never regenerate. Unrecognized tags inside an existing
`otrk` must be preserved verbatim.

`serato_tools.usb_export.copy_crates_to_usb` `shutil.rmtree`s the
destination `_Serato_` directory. Its own source even has a TODO:
merge with existing, instead of replacing. Do not use it.

## `neworder.pref` [verified]

`_Serato_/neworder.pref` is UTF-16BE plain text, crate display order.
The 80-byte single-crate example decodes to exactly:

```text
[begin record]
[crate]test
[end record]
```

Trailing newline present. One `[crate]<name>` line per crate, in
display order. `app/adapters/serato/neworder.py` reads and writes it.

## Hot cues, `Serato Markers2` GEOB [verified]

ID3v2.4 `GEOB` frame, description `Serato Markers2`.

Payload wrapper:

```text
[0x01][0x01][ base64 ASCII, may contain \n and trailing NULs ]
```

Strip `\r`, `\n`, `\x00`. If the remaining alphabet length is `4n+1`,
drop the last character. That leftover cannot encode a byte and is not
a truncated field. See
[ADR 0010](../decisions/0010-tolerate-leftover-markers2-base64.md).
Re-pad to a multiple of 4, base64-decode. Do not cut at 64 characters.
That would truncate `BPMLOCK`. The decoded blob is:

```text
[0x01][0x01] then repeated entries:
  [ name, NUL-terminated ASCII ][ u32 BE length ][ body ]
then a single trailing 0x00
```

Entry types observed: `COLOR`, `BPMLOCK`, `CUE`. Documented elsewhere
but not observed here: `LOOP`, `FLIP`.

`CUE` body, 13 bytes plus name:

| Offset | Size | Meaning |
|--------|------|---------|
| 0 | 1 | `0x00` |
| 1 | 1 | cue slot index, 0-based |
| 2 | 4 | position, u32 BE, milliseconds |
| 6 | 1 | `0x00` |
| 7 | 3 | RGB colour |
| 10 | 2 | `0x00 0x00` |
| 12 | .. | cue name, NUL-terminated. Empty in the sample |

`COLOR` body: `00 FF FF FF`. `BPMLOCK` body: `01`.

Verified end-to-end against Lexicon's own database:

| Lexicon `Cuepoint` | Serato `CUE` |
|--------------------|--------------|
| `startTime 0.0`, `position 0`, `magenta_red` | `slot=0 pos=0ms color=#CC0044` |
| `startTime 0.441`, `position 1`, `blue_light` | `slot=1 pos=441ms color=#0088CC` |

Seconds × 1000 becomes u32 BE. Rekordbox cue `position` becomes the
Serato slot index.

### Ground-truth blobs

Decoded `Serato Markers2` payload, `Techno1.BEFORE.wav` (30 bytes):

```text
0101 434f4c4f5200 00000004 00ffffff
     42504d4c4f434b00 00000001 01
     00
```

`Techno1.AFTER.wav` (72 bytes), the same plus two `CUE` entries:

```text
0101 434f4c4f5200 00000004 00ffffff
     42504d4c4f434b00 00000001 01
     43554500 0000000d 00 00 00000000 00 cc0044 0000 00
     43554500 0000000d 00 01 000001b9 00 0088cc 0000 00
     00
```

`0x1b9` = 441 ms. A writer is correct when applying AFTER's cue list
to BEFORE reproduces the AFTER payload byte-for-byte.

### Cue colour

Rekordbox stores RGB on PCP2. Serato shows that RGB. There is no
palette table to maintain. See
[ADR 0008](../decisions/0008-beatgrid-and-cue-sync-validated-in-serato.md).

## Beatgrid, `Serato BeatGrid` GEOB [verified format, not written by Lexicon]

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

`marker_count=1`, terminal `pos=0.0s`, `bpm=136.000` (`0x43080000`),
trailing `0x00`. This matched rekordbox's BPM of 136.0.

Lexicon does not write beatgrids. `Serato BeatGrid` and
`Serato Autotags` were byte-identical before and after on all four
experiment files. Only `Serato Markers2` changed, and only on the two
tracks that had cues. There is no Lexicon behaviour to copy here.
Beatgrids are authored from rekordbox ANLZ `PQTZ` data. That Lexicon
pair only showed single-marker grids. Multi-marker grids were
confirmed in Serato on 2026-08-30.

## `Serato Autotags` GEOB [verified]

`[0x01][0x01]` then three NUL-terminated ASCII strings: bpm, autogain,
gaindb.

```text
0101 "136.00"\0 "0.000"\0 "0.000"\0
```

## Tag container: MP3, WAV, AIFF, FLAC, MP4

| Container | Where the Serato payload lives |
|-----------|-------------------------------|
| MP3 | ID3v2 encapsulated-object frames at the head of the file. v2.2 uses 3-byte `GEO` ids and 3-byte sizes, no flags. v2.3 uses 4-byte `GEOB` and raw 32-bit sizes. v2.4 uses synchsafe sizes. A file that starts at an MPEG frame, no ID3, gets an ID3v2.4 tag prepended. |
| WAV | The ID3 stream is wrapped in a RIFF chunk with id `id3 `. The chunk must be rewritten and the RIFF size field fixed. A WAVE with no `id3 ` chunk gets one appended. |
| AIFF / AIFC | Same ID3 GEOB as MP3, in a big-endian `ID3 ` chunk. Audio is `SSND` after an 8-byte offset/blockSize header. A file with no ID3 chunk gets one. |
| FLAC | Vorbis comments `SERATO_BEATGRID` / `SERATO_MARKERS_V2`. Value is base64, no padding, newline every 72 characters, of `application/octet-stream\\0\\0` + description + payload. |
| MP4 / M4A | Freeform atoms `----:com.serato.dj:<name>`. `beatgrid` / `markersv2` / `markers` map to BeatGrid / Markers2 / Markers_. Decoded value is the same wrapper as FLAC. `markers` and `markersv2` wrap base64 every 72 characters. The others do not. The `markers` payload is not ID3 Markers_: raw `uint32` milliseconds, `0xFFFFFFFF` unset, 19-byte rows. Serato ignores pads 1-5 unless that layout is present. AAC encoder delay, iTunSMPB or 2112 samples, is subtracted from times so the grid sits on the first beat. |

Chunk order observed in the WAV fixtures: `fmt ` / `data` / `DISP` /
`iXML` / `_PMX` / `LIST` / `id3 `.

The Serato marker payloads are identical across containers. Only the
wrapper differs.

ID3 writes keep the original tag size when padding allows. An MP3 tag
with no `Serato Offsets_` may grow. A tagless MPEG MP3 or WAVE may
gain an ID3 tag. An AIFF `ID3 ` chunk may grow or be inserted. FLAC
comment blocks and MP4 `moov` may grow. STREAMINFO / `mdat` stay
byte-identical. Growing `moov` rewrites `stco` / `co64` so samples
still point at `mdat`.

Serato prefers `Serato Markers_` over Markers2 when both exist.
`Markers_` only stores the first five cues. Sync writes both so
leftover five-cue data cannot hide the Rekordbox pads. Cues 6-8 live
in Markers2 only. On M4A the same payloads are `markers` /
`markersv2`.

## Parser status

| Component | Status |
|-----------|--------|
| `DatabaseV2` read | [confirmed] serato-tools |
| `Crate` read | [confirmed] serato-tools |
| `Crate` write | [confirmed] serato-tools `add_track` + `save`, structurally valid TLV |
| `database V2` append | [confirmed] via `DatabaseV2.entries` + the private `_dump()`. `save()` writes `raw_data`, which only `_dump()` refreshes, so appending to `entries` alone is silently discarded |
| `neworder.pref` read/write | [confirmed] `app/adapters/serato/neworder.py` |
| GEOB tag read/write | [confirmed] `app/adapters/serato/tags.py`. `serato_tools` also ships `track_cues_v2`, `track_beatgrid`, `track_autotags`, unused |

## Mutation safety

| Rule | Status |
|------|--------|
| Never write under `PIONEER/` | required |
| Merge existing records, never regenerate | required |
| Preserve unrecognized TLV tags verbatim | required |
| Do not create or insert `location.sqlite` | required |
| Serato must not be running during a write | operator precondition |

Recovery is restoring the Rekordbox USB. There is no host rollback.

## Related

- [../adapters/serato.md](../adapters/serato.md)
- [../workflows/audio-commit.md](../workflows/audio-commit.md)
- [../workflows/m4a-markers.md](../workflows/m4a-markers.md)
