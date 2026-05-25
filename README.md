# Usbversal

Python CLI for **safe, metadata-only** manipulation of DJ library databases on USB-mounted media. Supports **Rekordbox** and **Serato**. No audio processing. No cloud dependency.

| | |
|--|--|
| **Platforms** | Windows, Linux (WSL supported) |
| **DJ systems** | Rekordbox (SQLite), Serato (proprietary; adapter-isolated) |
| **Primary test USB** | `/mnt/usb` (WSL) — see [docs/storage/usb-detection.md](docs/storage/usb-detection.md) |
| **Status** | Scaffolding — see [docs/state/repository-state.json](docs/state/repository-state.json) |

## Purpose

Usbversal helps DJs and tool authors inspect and modify library metadata on removable drives without corrupting vendor databases. All write paths require backup-first safety.

## Goals

- Detect USB-mounted DJ libraries (Rekordbox, Serato)
- List playlists, crates, and track metadata (database fields only)
- Apply safe writes with **mandatory backup and rollback**
- Run long operations as **async jobs** with progress events
- Ship as **PyInstaller executables** for Windows and Linux

## Safety guarantees

1. Full database file backup to `backups/<timestamp>/` before any write
2. Integrity checks when the adapter supports them (Rekordbox: SQLite `PRAGMA integrity_check`)
3. Writes rejected when backup cannot be created or verified
4. Rollback restores from backup metadata

## USB-based workflow

Development and validation use a mounted USB path:

```text
/mnt/usb
```

Use this mount only for integration validation tasks explicitly scoped in `docs/tasks/`. Do not assume it is always present.

## CLI usage

```bash
# Discovery
python -m app.cli scan --mount /mnt/usb

# Rekordbox playlists (exportLibrary.db via rbox)
python -m app.cli list-playlists --mount /mnt/usb
python -m app.cli list-playlists --mount /mnt/usb --json

# Backup (read-only copy to <mount>/backups/<timestamp>/)
python -m app.cli backup --mount /mnt/usb

# Rollback (restore from a prior backup; creates pre-rollback copy by default)
python -m app.cli rollback --mount /mnt/usb --backup-id 20260525T075946Z

# Serato crates (read-only)
python -m app.cli list-crates --mount /mnt/usb

# Copy Rekordbox playlist to Serato crate (backs up RB + Serato first)
python -m app.cli migrate-playlist --mount /mnt/usb --playlist-id 1 --dry-run
python -m app.cli migrate-playlist --mount /mnt/usb --playlist-name "Pocket"

# Copy BPM/key/beatgrid/hot cues into Serato MP3 tags (not database V2)
python -m app.cli sync-analysis --mount /mnt/usb --playlist-id 1 --dry-run

# Safety
usbversal backup --mount /mnt/usb --target ./backups/
usbversal rollback --mount /mnt/usb --backup-id <id>

# Writes (backup required)
usbversal apply --mount /mnt/usb --plan <file.json>

# Jobs
usbversal jobs list
usbversal jobs resume <job-id>
usbversal jobs cancel <job-id>
```

## Packaging intent

Distribution target is standalone executables via **PyInstaller**:

- `usbversal` CLI binary per platform
- Bundled Python runtime; no separate interpreter install required for end users

See [docs/decisions/0003-use-pyinstaller.md](docs/decisions/0003-use-pyinstaller.md).

## Project layout

| Path | Role |
|------|------|
| `app/` | Python package root |
| `app/cli/` | Thin CLI entrypoints (`python -m app.cli`) |
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

# Verify (always use .venv/bin/python or an activated shell)
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
.venv/bin/python -m app.cli scan --mount /mnt/usb
```

## Autonomous agents

Read [`AGENT.md`](AGENT.md) before any work. Update [`docs/state/`](docs/state/) after every task.

## License

TBD
