# Serato write-format ground truth

Byte-exact before/after pair from a controlled experiment on a Windows host
(2026-08-21): a Lexicon sync wrote hot cues into a rekordbox-sourced WAV.

| File | State |
|------|-------|
| `Techno1.BEFORE.wav` | `Serato Markers2` holds only `COLOR` + `BPMLOCK` |
| `Techno1.AFTER.wav` | same file after Lexicon wrote 2 hot cues |

The **only** difference is the `Serato Markers2` GEOB payload. `Serato BeatGrid`
and `Serato Autotags` are byte-identical in both — Lexicon does not write
beatgrids, so there is no reference behaviour to copy for those.

Decoded expectations are recorded in
[docs/schemas/serato-schema-notes.md](../../../docs/schemas/serato-schema-notes.md).
Use this pair to assert round-trip equality for any `Serato Markers2` writer:
writing the AFTER cue list onto BEFORE must reproduce AFTER's payload exactly.

These are WAV, so they also exercise the RIFF `id3 ` chunk path (the ID3 stream
is wrapped in a RIFF chunk, not at the head of the file as in MP3).

Audio content is a ~1 s Pioneer GROOVE CIRCUIT factory sample loop, retained
only as a tag container.
