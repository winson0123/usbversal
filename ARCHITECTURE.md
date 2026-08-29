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
│                      Job Orchestrator                       │
│           async jobs · progress · cancel · resume           │
└───────┬──────────────────────────────┬────────────────────┘
        │                              │
┌───────▼────────┐              ┌──────▼───────┐
│  Core Domain   │              │   Events     │
│ models · plans │◄────────────►│  bus / log   │
└───────┬────────┘              └──────────────┘
        │
┌───────▼────────────────────────────────────────────────────┐
│                    Adapter Layer                           │
│  ┌─────────────────┐      ┌─────────────────┐            │
│  │ RekordboxAdapter│      │  SeratoAdapter  │            │
│  │ SQLite · schema │      │ binary · TBD    │            │
│  └────────┬────────┘      └────────┬────────┘            │
└───────────┼────────────────────────┼─────────────────────┘
            │                        │
┌───────────▼────────────────────────▼─────────────────────┐
│                   Storage Layer                          │
│  USB detection · host paths                              │
└──────────────────────────┬───────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  USB mount  │
                    │  DJ DB files│
                    └─────────────┘
```

## Module Separation Philosophy

| Layer | Responsibility | Must not |
|-------|----------------|----------|
| TUI | Screens, rendering, key handling | Parse DB formats |
| Core | Domain models, validation, plans | Touch vendor-specific bytes |
| Adapters | Vendor read/write, schema mapping | Manage mount detection |
| Jobs | Long-running work, cancellation | Embed vendor SQL in the TUI |
| Storage | Paths, USB mounts, host data dir | Interpret playlist semantics |

Dependencies flow **inward**: TUI → Jobs → Services → Adapters → Storage → Core.
`core` holds domain types and imports nothing from the other layers. TUI is a
thin presentation layer, permitted `jobs`, `services`, and `core`, enforced by
`test_architecture.py` — see [ADR 0009](docs/decisions/0009-use-textual-for-the-tui.md).

**Vendor libraries (`rbox`, `serato-tools`) may only be imported inside `app/adapters/`.**
Services that need vendor data call an adapter function instead, which keeps schema
handling in one place and gives tests a seam that is not a vendor class.

## Adapter Pattern (Rekordbox / Serato)

Each vendor implements a common adapter interface (to be defined in `core/`):

- `detect(library_root) -> bool`
- `read_metadata(...) -> DomainModel`
- `apply_plan(plan) -> Result` — writes go immediately; Rekordbox USB restore is the recovery path

Adapters isolate:

- Schema version differences
- Unknown column/field preservation
- Vendor-specific integrity checks

See `docs/adapters/rekordbox.md` and `docs/adapters/serato.md`.

## Event System Concept

Operations emit structured events for logging, TUI progress, and subscribers:

| Event type | Examples |
|------------|----------|
| Progress | `job.progress`, `scan.found_library` |
| Warning | `db.locked`, `schema.unknown_field` |
| Error | `integrity.failed` |
| Lifecycle | `job.started`, `job.completed`, `job.cancelled` |

Events are immutable dataclasses; subscribers must not block the job runner.

Details: `docs/architecture/event-system.md`.

## Async Job Model Concept

Long operations (scan, apply) run as **asyncio tasks** managed by a job registry:

- Persistent job ID and checkpoint metadata (for resumability)
- Cooperative cancellation
- Progress callbacks via event bus

Details: `docs/architecture/async-model.md`, `docs/jobs/`.

## Write Safety Model

```text
apply requested
    → adapter.verify_integrity (if supported)
    → adapter.apply_plan(plan)
```

Writes go immediately. Recovery is restoring the Rekordbox USB. `PIONEER/` is never written. Tag writes verify audio hash and frame read-back before the new file replaces the old one.

## Technology Choices

| Decision | ADR |
|----------|-----|
| Python | [0001-use-python-cli.md](docs/decisions/0001-use-python-cli.md) |
| asyncio jobs | [0002-use-asyncio.md](docs/decisions/0002-use-asyncio.md) |
| PyInstaller packaging | [0003-use-pyinstaller.md](docs/decisions/0003-use-pyinstaller.md) |
| Textual for the TUI | [0009-use-textual-for-the-tui.md](docs/decisions/0009-use-textual-for-the-tui.md) |
| Tolerate leftover Markers2 base64 | [0010-tolerate-leftover-markers2-base64.md](docs/decisions/0010-tolerate-leftover-markers2-base64.md) |

## Machine-Readable Architecture State

Constraints and allowed patterns: `docs/state/architecture-state.json`.

## Further Reading

- [docs/architecture/system-overview.md](docs/architecture/system-overview.md)
- [docs/workflows/](docs/workflows/)
