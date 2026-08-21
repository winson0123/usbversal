# Serato Index Bootstrap (Stage 1 — Planning)

**Status:** planned — TASK-071 … TASK-076
**Related:** [ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md),
[serato-schema-notes.md](../schemas/serato-schema-notes.md),
[playlist migration](rekordbox-to-serato-playlist-migration.md)

## The gap this closes

`migrate-playlist` today can only write tracks that **Serato already knows
about**. [`app/services/migration_service.py`](../../app/services/migration_service.py)
builds its crate from `build_serato_path_index(serato_db.get_track_paths())` and
drops anything absent from that index into `skipped_paths`; if `_Serato_` does
not exist at all it raises `SeratoLibraryRequiredError` and stops.

So on a **plain rekordbox stick — the actual target of this project — usbversal
does nothing.** The `/mnt/usb` validation reported `skipped=0` only because
Lexicon had already populated that stick with 793 tracks.

Stage 1 makes usbversal author the Serato index itself. It writes only inside
`_Serato_/` and **never touches `PIONEER/` or the audio under `Contents/`**.

## Mission

```text
D:\PIONEER\      rekordbox owns this — leave alone
D:\Contents\     the audio — shared, untouched by Stage 1
D:\_Serato_\     Serato owns this — we write here
```

Two indexes over the same audio. Nothing duplicated, nothing moved, no lossy
round-trip — the formats occupy disjoint directories.

## Pipeline

```text
1. backup  _Serato_/{database V2, *.crate, neworder.pref}   TASK-071
2. read    rekordbox playlist + track metadata via rbox
3. map     content.path -> pfil   (strip one leading '/')
4. merge   database V2: existing otrk by pfil, add/update ours   TASK-073
5. write   Subcrates/<name>.crate, playlist order preserved      TASK-075
6. merge   neworder.pref, preserving existing crate order        TASK-074
```

## Design constraints

| Constraint | Source |
|------------|--------|
| Merge existing records, never regenerate | stick already carries a real 522 KB `database V2` |
| Preserve unrecognized TLV tags verbatim | `unknown_field_preservation` |
| `pfil` / `ptrk` are drive-relative, no leading slash, forward slashes | [verified] |
| `tbpm` is a **string**, 2dp | [verified] |
| Crate track order = `otrk` sequence | [verified] |
| Never use `serato_tools.usb_export.copy_crates_to_usb` | it `rmtree`s the destination `_Serato_` |

## Field mapping — rekordbox → `otrk`

The verified minimal record is in
[serato-schema-notes.md](../schemas/serato-schema-notes.md#database-v2-verified).
Rekordbox One Library supplies title, artist, album, genre, bpm, key, duration,
bitrate, and file size; `ttyp` is `mp3` for a USB export. Fields with no
rekordbox source (`tgrp`, `trmx`, `tlbl`, `tcmp`, `ttyr`) are written empty, as
Lexicon does.

## Open questions

1. Does `serato-tools` `DatabaseV2` support **appending a new track record**, or
   only modifying existing ones? Its `modify_and_save` path is built around
   existing entries. If it cannot append while preserving unknown tags, usbversal
   needs its own TLV codec (TASK-072) — the format is small and fully specified.
2. What does Serato do with a crate referencing a `pfil` that is in
   `database V2` but whose audio it has never analyzed? Expected: shows the
   track, no waveform until analyzed. Unverified.
3. Should the existing `Contents.crate` / Lexicon-written `Pocket.crate` be
   preserved, merged, or regenerated? Default: **preserve, never rewrite without
   an explicit flag.**
4. Does Serato re-read `database V2` on mount, or cache? Lexicon rewrites
   `neworder.pref` on every sync, which suggests the crate list is read fresh.

## Verification

- Round-trip every written file through an independent decoder and assert
  structural equality (`vrsn` first, `otrk` count, path round-trip).
- Diff `database V2` before/after: existing records must be **byte-identical**
  except where intentionally updated.
- Mount the stick in Serato: crate appears, order correct, BPM and key correct.
- Mount in rekordbox / CDJ: rekordbox side **unchanged** (hash `PIONEER/` before
  and after).
