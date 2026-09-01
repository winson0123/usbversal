# System overview

The product is the TUI: Home → Library → Progress → Done.

Usbversal reads Rekordbox playlists from a USB stick and writes Serato
crates, index rows, and analysis tags onto that same stick. The TUI
never opens a vendor database itself.

## Layers

| Layer | Package | Role |
|-------|---------|------|
| TUI | `app.tui` | Screens and keys. Dispatch only. |
| Services | `app.services` | Open the library, sync playlists, write tags |
| Core | `app.core` | Models and playlist trees |
| Adapters | `app.adapters` | Rekordbox read, Serato read and write |
| Storage | `app.storage` | Mount scan, host paths |

## Read

```text
TUI Home
  → Storage auto-detect (/media/$USER, /Volumes, drive letters)
    → probe_mount + prepare_library
      → Library screen
```

## Write

```text
TUI Progress
  → sync_playlists (index, analysis tags, crates)
  → flush_mount
```

Set `USBVERSAL_MOUNT` when auto-detect misses the stick.

## Boundaries

- Core does not import SQLite or Serato parsers.
- Adapters do not enumerate mounts. Storage does.
- The TUI does not own vendor parsers.
- Services do not import `rbox` or `serato-tools`.

See [../../ARCHITECTURE.md](../../ARCHITECTURE.md).
