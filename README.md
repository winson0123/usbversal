# Usbversal

Python CLI for **safe, metadata-only** manipulation of DJ library databases on USB-mounted media. Supports **Rekordbox** and **Serato**. No audio processing. No cloud dependency.

| | |
|--|--|
| **Platforms** | Windows, Linux (WSL supported) |
| **DJ systems** | Rekordbox (SQLite), Serato (proprietary; adapter-isolated) |
| **Primary test USB** | `/mnt/usb` (WSL) — see [docs/storage/usb-detection.md](docs/storage/usb-detection.md) |
| **Status** | Read paths + backup/rollback working; Serato index authoring in progress — see [docs/state/repository-state.json](docs/state/repository-state.json) |

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

The `usbversal` binary and `python -m app.cli` accept the same commands. The
current argparse interface is a **harness for testing the underlying services**;
the shipped tool is an interactive terminal UI, built on `textual`
([ADR 0009](docs/decisions/0009-use-textual-for-the-tui.md)). Its full
Waiting → Detect → Library → Progress → Done flow is wired end to end (see
[docs/planning/interactive-tui.md](docs/planning/interactive-tui.md)),
though not yet validated against real hardware:

```bash
usbversal tui
# or
python -m app.tui
```

### Read-only

```bash
python -m app.cli scan --mount /mnt/usb
python -m app.cli list-playlists --mount /mnt/usb [--json]
python -m app.cli list-crates --mount /mnt/usb [--json]
```

### Safety

```bash
python -m app.cli backup --mount /mnt/usb [--target ./backups/]
python -m app.cli rollback --mount /mnt/usb --backup-id 20260525T075946Z
```

### Writes (backup required)

```bash
python -m app.cli migrate-playlist --mount /mnt/usb --playlist-name "Pocket" --dry-run
python -m app.cli apply --mount /mnt/usb --plan plans/pocket.json --dry-run
```

Every write path builds a `WriteContext`, which refuses to construct unless the
backup directory exists, carries a readable manifest, and passes checksum
verification. After migrating a crate, run **Analyze Files** in Serato (offline)
so it builds BPM, beatgrid, and cues — usbversal does not yet write those tags
([Stage 2](docs/planning/rekordbox-to-serato-analysis-sync.md)).

### Jobs

```bash
python -m app.cli jobs list
python -m app.cli jobs resume <job-id>
python -m app.cli jobs cancel <job-id>
```

See [docs/workflows/usb-integration-validation.md](docs/workflows/usb-integration-validation.md)
for the full `/mnt/usb` checklist.

## Packaging intent

Distribution target is standalone executables via **PyInstaller**:

- `usbversal` CLI binary per platform
- Bundled Python runtime; no separate interpreter install required for end users

```bash
./scripts/build-release.sh   # Linux → dist/usbversal
./dist/usbversal --help
```

See [docs/workflows/release-workflow.md](docs/workflows/release-workflow.md) and [docs/decisions/0003-use-pyinstaller.md](docs/decisions/0003-use-pyinstaller.md).

## Project layout

| Path | Role |
|------|------|
| `app/` | Python package root |
| `app/cli/` | Thin CLI entrypoints (`python -m app.cli`) — test harness for the service layer |
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
