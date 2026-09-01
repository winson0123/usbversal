# Usbversal architecture

How the TUI is split. Details live under `docs/architecture/`.

## Overview

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
│  Core domain   │              │     Adapters      │
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

## Layers

| Layer | Does | Must not |
|-------|------|----------|
| TUI | Screens, keys | Parse DJ databases |
| Services | Sync, bootstrap, progress | Import `rbox` or `serato-tools` |
| Core | Models and playlist trees | Touch vendor bytes |
| Adapters | Vendor read and write | Enumerate mounts |
| Storage | Paths, USB, host dir | Decide playlist meaning |

Imports go inward: TUI → services → adapters → storage → core.
`core` imports none of the others. The TUI may import `services` and
`core`. `tests/test_architecture.py` fails a commit that breaks that.
See [ADR 0009](docs/decisions/0009-use-textual-for-the-tui.md).

`rbox` and `serato-tools` stay inside `app/adapters/`.

## Adapters

Rekordbox is read-only (`exportLibrary.db`). Serato gets crate files,
appended `database V2` records, updates to rows that already exist in
`location.sqlite`, and beatgrid / hot-cue tags on the audio files.

See `docs/adapters/rekordbox.md` and `docs/adapters/serato.md`.

## Writes

```text
sync requested
    → verify tag rewrite (hash + read-back)
    → replace audio / crate / index files
    → flush the mount
```

Writes land immediately. Recovery is restoring the Rekordbox USB.
Nothing under `PIONEER/` is written. `location.sqlite` is updated in
place on rows Serato already has. We never create that file or insert
into it.

## Decisions

| Decision | ADR |
|----------|-----|
| Python | [0001-use-python.md](docs/decisions/0001-use-python.md) |
| asyncio and a Rekordbox thread | [0002-use-asyncio.md](docs/decisions/0002-use-asyncio.md) |
| PyInstaller | [0003-use-pyinstaller.md](docs/decisions/0003-use-pyinstaller.md) |
| rbox | [0004-use-rbox-rekordbox-reader.md](docs/decisions/0004-use-rbox-rekordbox-reader.md) |
| serato-tools | [0005-use-serato-tools.md](docs/decisions/0005-use-serato-tools.md) |
| Beatgrid and cue writes | [0008-beatgrid-and-cue-sync-validated-in-serato.md](docs/decisions/0008-beatgrid-and-cue-sync-validated-in-serato.md) |
| Textual | [0009-use-textual-for-the-tui.md](docs/decisions/0009-use-textual-for-the-tui.md) |
| Leftover Markers2 base64 | [0010-tolerate-leftover-markers2-base64.md](docs/decisions/0010-tolerate-leftover-markers2-base64.md) |

Constraints in JSON: `docs/state/architecture-state.json`.

More: [docs/architecture/system-overview.md](docs/architecture/system-overview.md),
[docs/workflows/](docs/workflows/).
