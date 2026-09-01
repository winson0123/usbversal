# ADR 0001: Use Python

**Status:** accepted
**Date:** 2026-05-22

## Context

Usbversal must manipulate DJ library metadata on USB drives across Windows,
Linux, and macOS. The tool needs rapid iteration, strong ecosystem support
for SQLite (Rekordbox), and straightforward packaging for non-developer DJs.

Alternatives considered: Rust (performance, single binary), Go (simple
deployment), Node (ecosystem but weaker SQLite ergonomics).

## Decision

Implement Usbversal as a **Python 3.11+ TUI** with an `app/` package layout,
`pytest` for tests, and `ruff` for lint/format.

## Consequences

### Positive

- Fast development for adapter prototyping and schema exploration
- Excellent SQLite support via stdlib `sqlite3`
- Large ecosystem for TUI and packaging
- Autonomous agents widely trained on Python project patterns

### Negative

- Requires PyInstaller (ADR 0003) for standalone binaries
- GIL limits CPU parallelism; mitigated by a dedicated Rekordbox thread
  and a small analysis worker pool
- Runtime dependency management via `pyproject.toml` discipline

### Neutral

- Performance is sufficient for metadata-only operations (not audio processing)
