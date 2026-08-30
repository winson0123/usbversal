# Audio file commit

`write_geob` rebuilds the file in memory and verifies the audio hash plus
frame read-back before any byte is meant to reach the live path.

`read_geob` and the skip path read only the tag. WAV ``data``, MPEG
frames, AIFF ``SSND``, FLAC audio, and MP4 ``mdat`` are seeked past so
a 50 MB song is not pulled to decide BeatGrid already matches
(TASK-297). A rewrite still loads the whole file.

When the rebuilt file is the same length (padded MP3 / existing WAV
`id3 `), only the changed span is written in place and fsynced. No
sibling `.tmp`, no `replace`. A failed patch writes that span back from
the in-memory original.

A WAVE with no `id3 ` chunk grows only at the end: the RIFF size at
offset 4 and a new chunk after EOF. The `data` chunk does not move.
That commit patches those four bytes and appends the tail (TASK-296).
A failed append restores the original size and RIFF size.

A WAVE whose `id3 ` already sits after `data` may grow that chunk
(TASK-312). Rekordbox often writes a tight tag with a `LIST` after it;
enlarging `id3 ` shifts only that metadata tail. The commit patches the
RIFF size and rewrites from the first changed byte after `data`. A
failed tail write restores the original RIFF size, overwritten tail, and
length. An `id3 ` that sits before `data` still refuses to grow.

Other size-changing writes still use a sibling `.tmp` and
`Path.replace` (TASK-286). A tagless MPEG MP3 (frame sync at byte 0,
no ID3v2) gets an ID3v2.4 tag prepended, so the audio moves and that
path still replaces. A RIFF file that is not WAVE is still rejected.

On exFAT that replace is not atomic. The destination can be truncated
before the new bytes land. A re-sync after TASK-285 left every track in
`WONSIN%%Gigs%%pocket 29aug2026` at 0 bytes.

TASK-286:

- Refuse an empty source file.
- Refuse a rebuilt file that is empty or less than half the original size.
- Write the `.tmp`, flush, and fsync; check its size before the swap.
- After the swap, fsync the live file and its parent directory.
- If the destination is missing or short after the swap, write the original
  bytes back.
- If the destination is empty and a leftover `.tmp` has bytes, promote the
  `.tmp` before the next write.

Recovery of a wiped song is still restoring the Rekordbox USB (or another
copy). This path only keeps a failed swap from destroying the file that
was just read.

## Crate, database V2, neworder (TASK-287)

The same swap without fsync left every `_Serato_` file at 0 bytes after a
fresh export was synced and the stick disconnected at 03:35 (`lost async
page write`; remount: `Volume was not properly unmounted`). Windows then
offered scan-and-fix. Contents was intact.

`write_crate` also unlinked the live `.crate` before `Crate.save`. A
zero-byte `database V2` still counted as a present library, so bootstrap
would not recreate the header.

Crate, database V2, and `neworder.pref` now go through `replace_flushed`.
A zero-byte `database V2` is treated as missing. After the swap,
`replace_flushed` fsyncs the parent directory. `sync_playlists` then
`flush_mount`s the volume (`syncfs`). Unmount yourself before
Windows/Serato; the TUI does not eject. See
`docs/workflows/volume-flush.md`.

Reading a leftover 0-byte `.crate` used to crash the Library screen
(`Crate()`: `version not set after parsing file`). `read_crate_track_paths`
returns no tracks for an empty or unparseable file (TASK-288).
