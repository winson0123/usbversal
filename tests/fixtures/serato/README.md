# Serato write-format ground truth

Byte-exact before/after pair from a controlled run on a Windows host
(2026-08-21). A Lexicon sync wrote hot cues into a Rekordbox-sourced WAV.

| File | State |
|------|-------|
| `Techno1.BEFORE.wav` | `Serato Markers2` holds only `COLOR` + `BPMLOCK` |
| `Techno1.AFTER.wav` | same file after Lexicon wrote 2 hot cues |

The only difference is the `Serato Markers2` GEOB payload. `Serato BeatGrid`
and `Serato Autotags` are byte-identical in both. Lexicon does not write
beatgrids, so there is no reference behaviour to copy for those.

Decoded expectations are in
[docs/schemas/serato-schema-notes.md](../../../docs/schemas/serato-schema-notes.md).
Writing the AFTER cue list onto BEFORE must reproduce AFTER's payload
exactly.

These are WAV, so they also hit the RIFF `id3 ` chunk path. The ID3
stream sits in a RIFF chunk, not at the head of the file as in MP3.

Audio is a ~1 s Pioneer GROOVE CIRCUIT factory sample, kept only as a
tag container.
