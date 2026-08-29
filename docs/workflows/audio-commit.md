# Audio file commit

`write_geob` rebuilds the file in memory and verifies the audio hash plus
frame read-back before any byte is meant to reach the live path. The live
swap still uses a sibling `.tmp` and `Path.replace`.

On exFAT that replace is not atomic. The destination can be truncated
before the new bytes land. A re-sync after TASK-285 left every track in
`WONSIN%%Gigs%%pocket 29aug2026` at 0 bytes.

TASK-286:

- Refuse an empty source file.
- Refuse a rebuilt file that is empty or less than half the original size.
- Write the `.tmp`, flush, and fsync; check its size before the swap.
- If the destination is missing or short after the swap, write the original
  bytes back.
- If the destination is empty and a leftover `.tmp` has bytes, promote the
  `.tmp` before the next write.

Recovery of a wiped song is still restoring the Rekordbox USB (or another
copy). This path only keeps a failed swap from destroying the file that
was just read.
