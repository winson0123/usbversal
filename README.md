# Usbversal

Usbversal is a terminal app that copies Rekordbox playlists, beatgrids,
and hot cues onto the Serato side of the same USB stick. The audio
stays put. Rekordbox files under `PIONEER/` stay put. Nothing talks
to the network.

Export the library from Rekordbox onto the stick first. Then run
usbversal, pick playlists, and sync. Unmount the stick on this machine
before Serato or Windows opens it.

## Use it

```bash
usbversal
# or, from a checkout
python -m app.tui
```

Windows, Linux, and macOS. The TUI watches the usual removable-media
roots (`/media/$USER`, `/Volumes`, drive letters). If the scanner
misses the stick, type the mount path, or set `USBVERSAL_MOUNT` before
launch.

Quit with `Ctrl+Q`.

## Screens

Home looks for a Rekordbox USB. A valid stick has
`PIONEER/rekordbox/exportLibrary.db`. Older DeviceSQL-only sticks
(`export.pdb` alone) are rejected. If nothing shows up, press Enter to
scan again, or type a path. Tab cycles matching folders.

Library is the playlist tree. Each row is red, yellow, or green:
nothing synced, some tracks synced, all tracks synced. Space selects a
playlist. `Ctrl+A` selects every playlist. `e` expands or collapses a
folder. Enter starts the sync.

Progress writes crates, then tags, then the Serato index. Done shows
counts. Failed tracks stay on that screen and also land in
`~/.local/share/usbversal/<volume>/error.log`. Enter goes back to
Library.

## How a sync works

1. Home finds the stick and opens the Rekordbox export read-only.
2. If the stick has no Serato library yet, usbversal creates an empty
   `_Serato_` folder so there is somewhere to write.
3. Library compares each Rekordbox playlist to crates already on the
   stick.
4. Progress copies the selected playlists into Serato crates, writes
   beatgrids and cues onto the audio files, and updates Serato's
   library list where a row already exists.
5. The mount is flushed. Unmount it yourself. The TUI does not eject.

A playlist becomes a crate named after the stick, then the Rekordbox
folders: `WONSIN%%Gigs%%Played`. Serato shows that as a folder tree
under the volume name. A slash in a playlist name stays a slash in the
crate title. It does not become another folder.

Tracks are matched by their path on the stick. Rekordbox stores
`/Contents/Artist/track.mp3`. Serato stores `Contents/Artist/track.mp3`.
Same file, one leading slash stripped. The song is not copied.

Beatgrids and hot cues come from Rekordbox analysis next to the
export. Those values are written into Serato's own tags on the file.
Cue colour is the RGB Rekordbox already stored. If Serato already has
the track in `location.sqlite`, the library-list BPM and key are
updated to match. Usbversal never creates that database or inserts
new rows. The first time Serato opens the stick, it builds that index
itself from `database V2`.

Writes merge. Existing Serato records are updated, not rebuilt from
scratch. A tag rewrite is checked against the audio hash and read back
before the live file is replaced. If that swap fails, the original
bytes go back.

If a sync goes wrong, restore the Rekordbox USB. That is the recovery
plan. There is no host rollback.

## Build

A `v*` tag on `main` builds Windows, macOS, and Linux binaries. On
this machine:

```bash
./scripts/build-release.sh
```

That writes `dist/usbversal` or `dist/usbversal.exe`. See
[docs/workflows/release-workflow.md](docs/workflows/release-workflow.md).

## Contribute

Agents start at [`AGENT.md`](AGENT.md). People changing code start at
[`CONTRIBUTING.md`](CONTRIBUTING.md). Layout and internals live in
[`ARCHITECTURE.md`](ARCHITECTURE.md) and [`docs/`](docs/).
