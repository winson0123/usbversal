# Hot cue colour and Markers_

## PCP2 RGB offset (TASK-253 / TASK-285)

Real Rekordbox `.EXT` PCP2 bodies are 72 bytes. A `00` sits at offset 28;
RGB is at **offset 29**:

    00 00 00 00 00 RR GG BB 00 00   (bytes 24-33)

TASK-253 read offset 28, so every colour dropped its red and shifted
(`#FF0017` became `#00FF00`; slot 6 `#0000FF` became black).

Confirmed 2026-08-30 on WONSIN `Young Wild and Free` (`ANLZ0000.EXT` under
`P037/0002E377`). Shorter test bodies still use offset 28.

## `Serato Markers_` (TASK-285)

Serato prefers `Markers_` over Markers2 when both exist. `Markers_` only
holds the first five cues. Leftover pads from an earlier Serato analyse
hide the Markers2 times and colours on the deck (library list still shows
all eight from Markers2).

Sync now rewrites `Markers_` for slots 0-4 whenever it writes Markers2.
Cues 6-8 stay Markers2-only.

## M4A track colour (TASK-299)

MP4 `markers` ends with a track-colour footer (`00` + RGB). That field
is not a cue. Writing `00 00 FF FF FF 00 00` made Serato paint the
jog `#00FFFF`. The footer is now `00 FF FF FF` (no colour). Markers2
`COLOR` is forced to the same unset value on every cue write.

Cue pads use Rekordbox RGB, same as MP3. TASK-299 briefly mapped
`#00C4FF` / `#FF0017` onto Lexicon's Serato palette on M4A only;
that is reverted.
