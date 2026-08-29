# System Overview

**Status:** TUI product; Waiting → Detect → Library → Progress → Done.

## Purpose

Usbversal provides a unified Python interface to read and safely modify DJ
library metadata on removable USB storage, without coupling the TUI to
vendor-specific database formats.

## Layers

| Layer | Package | Role |
|-------|---------|------|
| TUI | `app.tui` | Screens and keys; dispatch only |
| Jobs | `app.jobs` | Progress rate tracking (JobRunner unused by the TUI) |
| Core | `app.core` | Domain models, plans, adapter protocols |
| Adapters | `app.adapters` | Rekordbox (SQLite), Serato (binary) |
| Storage | `app.storage` | Mount scan, host data paths |
| Services | `app.services` | Scan, playlist/crate orchestration |

## Data Flow (Read)

```text
TUI Detect
  → Storage auto-detect (/media/$USER, /Volumes, drive letters)
    → Adapter.detect + Adapter.read_metadata
      → Library screen
```

## Data Flow (Write)

```text
TUI Progress
  → sync_playlists (index, analysis, crates)
```

`USBVERSAL_MOUNT` is a silent escape hatch when auto-detect misses a path.

## Boundaries

- **Core** never imports SQLite or Serato-specific parsers directly.
- **Adapters** never perform mount enumeration (Storage responsibility).
- **TUI** never owns vendor parsers.

## Related

- [async-model.md](async-model.md)
- [event-system.md](event-system.md)
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
