# M4A cues and beatgrid

WONSIN M4As once carried `beatgrid`, `markersv2`, and `markers`. The
grid showed in Serato, slightly late. Pads 1-5 did not.

## `markers` is not ID3 Markers_

Serato only honours the first five M4A cues when they are also in the
`markers` atom, in the MP4 row layout: raw big-endian milliseconds,
`0xFFFFFFFF` unset, raw RGB. ID3 Markers_ (serato32 times, `0x7f` unset,
22-byte rows) is ignored. A leftover Serato `markers` atom overwritten
with the ID3 shape still hides Markers2.

Live check 2026-08-30, `otonoke_bootleg_lufs-10.m4a`: Serato-written
`markers` is 279 bytes. Cue 0 at 1456 ms is `00 00 05 b0` plus
`ffffffff` unused fields and `#CC0044`. The usbversal write was 318-byte ID3.

Sync now writes the MP4 row layout. `read_geob` still returns the ID3
shape so skip-checks stay one codec.

## Track colour footer

The bytes after the 14 rows are the track colour, not padding.
Mixxx and Serato parse `00` + RGB. `#FFFFFF` means no colour. The jog
stays dark.

An earlier write copied the 7-byte tail from the otonoke leftover
(`00 00 FF FF FF 00 00`). Serato reads the first four bytes as
`#00FFFF` and fills the jog cyan. That leftover colour showed up on
`Rock That Body (Lumarii Remix)`.

Sync now writes Mixxx's 4-byte unset footer `00 FF FF FF` (276-byte
payload). Markers2 always gets a `COLOR` of `00 FF FF FF` so a leftover
Serato colour cannot hide the footer.

Cue RGB stays in the 19-byte rows and is the same ANLZ value written
on MP3 (ADR 0008). Do not snap it to Lexicon's Serato palette.

## AAC encoder delay

Rekordbox ANLZ times include priming. Serato's M4A waveform starts at
the first decoded sample. Writing the ANLZ time puts the grid to the
right of the first beat.

`otonoke` `iTunSMPB` delay is `0x840` (2112 samples) at 44100 Hz, about
48 ms. The first ANLZ beat is 47 ms. Files without `iTunSMPB` use 2112
samples and the `mdhd` timescale (44 ms at 48000 Hz).

Sync subtracts that delay from beats and cues before encoding. Times
are clamped at 0.

The pad that showed the bug: `Rock That Body (Lumarii Remix)`. One hot
cue on the first beat (ANLZ 70 ms).
