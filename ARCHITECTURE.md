# Usbversal Architecture

High-level architecture for the Python DJ-library TUI. Implementation details live under `docs/architecture/`.

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                         TUI (thin)                          │
│           Home → Library → Progress → Done                  │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                       Services                              │
│     open library · sync playlists · analysis tags           │
└───────┬──────────────────────────────────┬──────────────────┘
        │                                  │
┌───────▼────────┐              ┌──────────▼────────┐
│  Core Domain   │              │     Adapters      │
│ models · trees │              │ Rekordbox · Serato│
└────────────────┘              └──────────┬────────┘
                                           │
                                ┌──────────▼────────┐
                                │     Storage       │
                                │ USB mounts · host │
                                └──────────┬────────┘
                                           │
                                    ┌──────▼──────┐
                                    │  USB mount  │
                                    │  DJ DB files│
                                    └─────────────┘
```

## Module Separation

| Layer | Responsibility | Must not |
|-------|----------------|----------|
| TUI | Screens, rendering, key handling | Parse DB formats |
| Services | Sync, bootstrap, progress callbacks | Import vendor libraries |
| Core | Domain models and playlist trees | Touch vendor-specific bytes |
| Adapters | Vendor read/write, schema mapping | Manage mount detection |
| Storage | Paths, USB mounts, host data dir | Interpret playlist semantics |

Dependencies flow **inward**: TUI → Services → Adapters → Storage → Core.
`core` holds domain types and imports nothing from the other layers. TUI is a
thin presentation layer, permitted `services` and `core`, enforced by
`test_architecture.py` — see [ADR 0009](docs/decisions/0009-use-textual-for-the-tui.md).

**Vendor libraries (`rbox`, `serato-tools`) may only be imported inside `app/adapters/`.**

## Adapters

Rekordbox is read-only (One Library `exportLibrary.db`). Serato writes crates,
appends `database V2`, updates existing `location.sqlite` rows, and writes
beatgrid / hot-cue tags on audio files.

See `docs/adapters/rekordbox.md` and `docs/adapters/serato.md`.

## Write Safety

```text
sync requested
    → verify tag rewrite (hash + read-back)
    → replace audio / crate / index files
    → flush the mount
```

Writes go immediately. Recovery is restoring the Rekordbox USB. `PIONEER/` is
never written. `location.sqlite` is updated in place on rows Serato already
has; it is never created or inserted into.

## Technology Choices

| Decision | ADR |
|----------|-----|
| Python | [0001-use-python.md](docs/decisions/0001-use-python.md) |
| asyncio + dedicated Rekordbox thread | [0002-use-asyncio.md](docs/decisions/0002-use-asyncio.md) |
| PyInstaller packaging | [0003-use-pyinstaller.md](docs/decisions/0003-use-pyinstaller.md) |
| rbox for Rekordbox reads | [0004-use-rbox-rekordbox-reader.md](docs/decisions/0004-use-rbox-rekordbox-reader.md) |
| serato-tools for crates | [0005-use-serato-tools.md](docs/decisions/0005-use-serato-tools.md) |
| Beatgrid and cue writes | [0008-beatgrid-and-cue-sync-validated-in-serato.md](docs/decisions/0008-beatgrid-and-cue-sync-validated-in-serato.md) |
| Textual for the TUI | [0009-use-textual-for-the-tui.md](docs/decisions/0009-use-textual-for-the-tui.md) |
| Leftover Markers2 base64 | [0010-tolerate-leftover-markers2-base64.md](docs/decisions/0010-tolerate-leftover-markers2-base64.md) |

## Machine-Readable Architecture State

Constraints and allowed patterns: `docs/state/architecture-state.json`.

## Further Reading

- [docs/architecture/system-overview.md](docs/architecture/system-overview.md)
- [docs/workflows/](docs/workflows/)
