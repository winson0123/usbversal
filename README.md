# Usbversal

Usbversal is a terminal app that copies Rekordbox playlists, beatgrids,
and hot cues onto the Serato side of the same USB stick. The audio
stays put. Rekordbox files under `PIONEER/` stay put.

Export the library from Rekordbox onto the stick first. Then run
usbversal, pick playlists, and sync. Unmount the stick on this machine
before Serato or Windows opens it.

## Use it

A built release is a single file. Launch it:

```bash
usbversal
```

Windows, Linux, and macOS. The TUI watches the usual removable-media
roots (`/media/$USER`, `/Volumes`, drive letters). If the scanner
misses the stick, type the mount path, or set `USBVERSAL_MOUNT` before
launch.

Quit with `Ctrl+Q`.

## Run from source

From a checkout, use the Python package. No release binary required.

```bash
./scripts/setup-dev.sh
source .venv/bin/activate

python -m app.tui
```

`setup-dev.sh` creates `.venv` and installs the package with the dev
extras. After that, `python`, `ruff`, and `pytest` are on `PATH` while
the venv is active.

```bash
ruff check .
ruff format --check .
pytest
```

Or call them as `.venv/bin/ruff` and `.venv/bin/pytest` without
activating. Same TUI, same screens, same `USBVERSAL_MOUNT` override.

Python 3.11 or newer. Task rules and review notes live in
[`CONTRIBUTING.md`](CONTRIBUTING.md). Agents start at
[`AGENT.md`](AGENT.md). Layout and internals live in
[`ARCHITECTURE.md`](ARCHITECTURE.md) and [`docs/`](docs/).

## Screens

Home looks for a Rekordbox USB. If nothing shows up, press Enter to
scan again, or type a path. Tab cycles matching folders.

Library is the playlist tree. Each row is red, yellow, or green:
nothing synced, some tracks synced, all tracks synced. Space selects a
playlist. `Ctrl+A` selects every playlist. `e` expands or collapses a
folder. Enter starts the sync.

Progress copies the playlists and writes grids and cues. Done shows
counts. Failed tracks stay on that screen and also land in
`~/.local/share/usbversal/<volume>/error.log`. Enter goes back to
Library.

## How a sync works

Home finds the stick and reads the Rekordbox playlists. If Serato has
never seen this stick, usbversal sets up an empty Serato library next
to the songs. Library then colours each playlist by how much of it is
already on the Serato side.

Progress takes the playlists you selected and writes them as Serato
crates. Folders stay folders, nested under the stick name. A Rekordbox
library on a volume called `MYUSB` shows in Serato like this:

```text
MYUSB
├── Gigs
│   └── Played
└── Genres
    └── Techno
```

The songs themselves are the same files already on the stick. Usbversal
matches each track by that path, then writes the Rekordbox beatgrid,
hot cues, and cue colours onto the file. BPM and key in Serato's
library list update for tracks Serato already knows. The first time
you open the stick in Serato, Serato finishes building its own list.

A later sync updates what is already there. It does not wipe the
Serato library. If writing a file fails, the original song is put
back. If a sync goes wrong, restore the Rekordbox USB.

Unmount the stick yourself when Done appears.

## Build

A `v*` tag on `main` builds Windows, macOS, and Linux binaries. On
this machine:

```bash
./scripts/build-release.sh
```

That writes `dist/usbversal` or `dist/usbversal.exe`. See
[docs/workflows/release-workflow.md](docs/workflows/release-workflow.md).
