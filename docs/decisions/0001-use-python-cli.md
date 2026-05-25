# ADR 0001: Use Python for CLI

**Status:** accepted  
**Date:** 2026-05-22

## Context

Usbversal must manipulate DJ library metadata on USB drives across Windows and Linux (WSL). The tool needs rapid iteration, strong ecosystem support for SQLite (Rekordbox), and straightforward packaging for non-developer DJs.

Alternatives considered: Rust (performance, single binary), Go (simple deployment), Node (ecosystem but weaker SQLite ergonomics for CLI tools).

## Decision

Implement Usbversal as a **Python 3.11+ CLI application** with an `app/` package layout, `pytest` for tests, and `ruff` for lint/format.

## Consequences

### Positive

- Fast development for adapter prototyping and schema exploration
- Excellent SQLite support via stdlib `sqlite3` or `aiosqlite`
- Large ecosystem for future GUI or scripting integrations
- Autonomous agents widely trained on Python project patterns

### Negative

- Requires PyInstaller (ADR 0003) for standalone binaries
- GIL limits CPU parallelism; mitigated by asyncio + thread offload for I/O
- Runtime dependency management via `pyproject.toml` discipline

### Neutral

- Performance sufficient for metadata-only operations (not audio processing)
