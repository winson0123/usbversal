# System Overview

**Status:** scaffolding — no runtime implementation yet.

## Purpose

Usbversal provides a unified Python interface to read and safely modify DJ library metadata on removable USB storage, without coupling CLI commands to vendor-specific database formats.

## Layers

| Layer | Package (planned) | Role |
|-------|-------------------|------|
| CLI | `usbversal.cli` | User-facing commands; argument parsing only |
| Jobs | `usbversal.jobs` | Async orchestration, progress, cancel/resume |
| Core | `usbversal.core` | Domain models, plans, adapter protocols |
| Adapters | `usbversal.adapters` | Rekordbox (SQLite), Serato (binary) |
| Storage | `usbversal.storage` | Mount scan, backup, atomic write, rollback |

## Data Flow (Read)

```text
CLI command
  → JobRunner.start(scan_job)
    → Storage.discover_libraries(/mnt/usb)
      → Adapter.detect + Adapter.read_metadata
        → Core.normalize → events → CLI output
```

## Data Flow (Write)

```text
CLI apply
  → JobRunner.start(apply_job)
    → Storage.backup(target_paths)
    → Adapter.apply_plan(plan, WriteContext)
      → on error: Storage.rollback
```

## Boundaries

- **Core** never imports SQLite or Serato-specific parsers directly.
- **Adapters** never perform mount enumeration (Storage responsibility).
- **Jobs** never format CLI tables (CLI responsibility).

## Related

- [async-model.md](async-model.md)
- [event-system.md](event-system.md)
- [cli-flow.md](cli-flow.md)
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
