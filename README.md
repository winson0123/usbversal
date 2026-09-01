# Usbversal

Interactive terminal UI for **safe, metadata-only** Rekordbox → Serato library
sync on USB-mounted media. No audio processing. No cloud dependency.

| | |
|--|--|
| **Platforms** | Windows, Linux, macOS |
| **DJ systems** | Rekordbox (One Library), Serato |
| **Mounts** | Auto-detect (`/media/$USER`, `/Volumes`, drive letters). `USBVERSAL_MOUNT` is a silent escape hatch. |
| **Status** | TUI Home → Library → Progress → Done |

## Purpose

Usbversal copies Rekordbox playlists, beatgrids, and hot cues onto a Serato
USB without touching Rekordbox files. Writes go immediately; recovery is
restoring the Rekordbox USB.

## Safety guarantees

1. Never write under `PIONEER/`. Recovery is restoring the Rekordbox USB.
2. Tag writes verify audio hash and frame read-back before the new file replaces the old one.
3. Failed sync items are listed on Done and written to host `error.log` (`~/.local/share/usbversal/<volume>/`).
4. Never regenerate a vendor index; merge only. Do not create or insert into `location.sqlite`.

## Usage

```bash
usbversal
# or
python -m app.tui
```

The TUI auto-detects a DJ USB, opens the library, and runs the sync.

## Packaging

Standalone executables via **PyInstaller**. A `v*` tag on `main` builds
Windows, macOS, and Linux artifacts and publishes a GitHub Release.

```bash
./scripts/build-release.sh   # this OS only → dist/usbversal[.exe]
```

See [docs/workflows/release-workflow.md](docs/workflows/release-workflow.md) and [docs/decisions/0003-use-pyinstaller.md](docs/decisions/0003-use-pyinstaller.md).

## Project layout

| Path | Role |
|------|------|
| `app/tui/` | The shipped product (`python -m app.tui`) |
| `app/core/` | Domain models |
| `app/adapters/` | Rekordbox / Serato adapters |
| `app/services/` | Scan, sync, analysis, crate writes |
| `app/storage/` | Mount detection, host data paths |
| `tests/` | Unit and integration tests |
| `docs/` | Architecture, ADRs, tasks, machine state |

## Documentation

| Audience | Start here |
|----------|------------|
| Autonomous agents | [`AGENT.md`](AGENT.md) |
| Architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Contributing | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Tasks | [`docs/tasks/current-task.md`](docs/tasks/current-task.md) |

## Development

```bash
./scripts/setup-dev.sh
source .venv/bin/activate

.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
.venv/bin/python -m app.tui
```

## Autonomous agents

Read [`AGENT.md`](AGENT.md) before any work. Update [`docs/state/`](docs/state/) after every task.
