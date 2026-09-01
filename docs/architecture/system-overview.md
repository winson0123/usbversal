# System Overview

**Status:** TUI product; Home → Library → Progress → Done.

## Purpose

Usbversal reads Rekordbox playlists from a USB stick and writes Serato crates,
index rows, and analysis tags onto the same stick, without coupling the TUI
to vendor-specific database formats.

## Layers

| Layer | Package | Role |
|-------|---------|------|
| TUI | `app.tui` | Screens and keys; dispatch only |
| Services | `app.services` | Open library, sync playlists, analysis tags |
| Core | `app.core` | Domain models and playlist trees |
| Adapters | `app.adapters` | Rekordbox (read) and Serato (read/write) |
| Storage | `app.storage` | Mount scan, host data paths |

## Data Flow (Read)

```text
TUI Home
  → Storage auto-detect (/media/$USER, /Volumes, drive letters)
    → probe_mount + prepare_library
      → Library screen
```

## Data Flow (Write)

```text
TUI Progress
  → sync_playlists (index, analysis tags, crates)
  → flush_mount
```

`USBVERSAL_MOUNT` is a silent escape hatch when auto-detect misses a path.

## Boundaries

- **Core** never imports SQLite or Serato-specific parsers directly.
- **Adapters** never perform mount enumeration (Storage responsibility).
- **TUI** never owns vendor parsers.
- **Services** never import `rbox` or `serato-tools`.

## Related

- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
