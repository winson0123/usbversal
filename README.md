# Usbversal

A terminal UI that copies Rekordbox playlists, beatgrids, and hot cues onto
the Serato side of a USB stick. It does not touch audio. It does not talk
to the network.

Usbversal does not write under `PIONEER/`. If a sync goes wrong, restore the
Rekordbox USB. That is the recovery plan. There is no host rollback.

| | |
|--|--|
| Platforms | Windows, Linux, macOS |
| DJ systems | Rekordbox One Library, Serato |
| Mounts | `/media/$USER`, `/Volumes`, drive letters. `USBVERSAL_MOUNT` when the scanner misses. |
| Screens | Home, Library, Progress, Done |

## What it will not do

1. Write under `PIONEER/`.
2. Replace an audio file until the tag rewrite matches the audio hash and
   reads back.
3. Create `location.sqlite` or insert rows into it. Existing rows get
   `bpm`, `key`, and `analysis_flags = 24`.
4. Rebuild a vendor index from scratch. Merge only.

Failed tracks show on Done and land in `~/.local/share/usbversal/<volume>/error.log`.

## Run it

```bash
usbversal
# or
python -m app.tui
```

Plug in a Rekordbox USB. Pick playlists. Sync.

## Build

A `v*` tag on `main` builds Windows, macOS, and Linux binaries and
publishes a GitHub Release. On this machine:

```bash
./scripts/build-release.sh
```

That writes `dist/usbversal` or `dist/usbversal.exe`. Details in
[docs/workflows/release-workflow.md](docs/workflows/release-workflow.md).

## Layout

| Path | Role |
|------|------|
| `app/tui/` | The product. `python -m app.tui` |
| `app/core/` | Domain models |
| `app/adapters/` | Rekordbox and Serato I/O |
| `app/services/` | Open, sync, analysis, crates |
| `app/storage/` | Mounts and host paths |
| `tests/` | pytest |
| `docs/` | Architecture, ADRs, tasks |

Agents start at [`AGENT.md`](AGENT.md). Humans who want to change code
start at [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Dev

```bash
./scripts/setup-dev.sh
source .venv/bin/activate

.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
.venv/bin/python -m app.tui
```
