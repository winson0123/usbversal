# Usbversal

Interactive terminal UI for **safe, metadata-only** Rekordbox → Serato library
sync on USB-mounted media. No audio processing. No cloud dependency.

| | |
|--|--|
| **Platforms** | Windows, Linux, macOS |
| **DJ systems** | Rekordbox (One Library), Serato |
| **Mounts** | Auto-detect (`/media/$USER`, `/Volumes`, drive letters). `USBVERSAL_MOUNT` is a silent escape hatch. |
| **Status** | TUI Waiting → Detect → Library → Progress → Done is wired end to end — see [docs/state/repository-state.json](docs/state/repository-state.json) |

## Purpose

Usbversal helps DJs copy Rekordbox playlists, beatgrids, and hot cues onto a
Serato USB without corrupting vendor databases. All write paths require
backup-first safety.

## Goals

- Detect USB-mounted DJ libraries (Rekordbox, Serato)
- Sync selected playlists into Serato crates with analysis tags
- Apply safe writes with **mandatory backup and rollback**
- Ship as **PyInstaller executables** for Windows, Linux, and macOS

## Safety guarantees

1. Full database file backup to `backups/<timestamp>/` before any write
2. Integrity checks when the adapter supports them
3. Writes rejected when backup cannot be created or verified
4. Rollback restores from backup metadata

## Usage

```bash
usbversal
# or
python -m app.tui
```

The TUI auto-detects a DJ USB, opens the library, and runs the sync. There is
no argparse command list.

## Packaging intent

Distribution target is standalone executables via **PyInstaller**:

```bash
./scripts/build-release.sh   # → dist/usbversal
```

See [docs/workflows/release-workflow.md](docs/workflows/release-workflow.md) and [docs/decisions/0003-use-pyinstaller.md](docs/decisions/0003-use-pyinstaller.md).

## Project layout

| Path | Role |
|------|------|
| `app/` | Python package root |
| `app/tui/` | The shipped product: interactive terminal UI (`python -m app.tui`) |
| `app/core/` | Domain models and events |
| `app/adapters/` | Rekordbox / Serato adapters |
| `app/services/` | Scan, backup, playlist/crate orchestration |
| `app/storage/` | Mount detection, backup, rollback |
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

Use the project virtual environment (required):

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

## License

TBD
