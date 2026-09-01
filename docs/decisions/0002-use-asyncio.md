# ADR 0002: Use asyncio for the TUI, with a dedicated Rekordbox thread

**Status:** accepted
**Date:** 2026-05-22

## Context

Opening a Rekordbox export and writing analysis tags are I/O-bound and
long-running. The TUI must stay responsive for progress, cancel, and
key handling. rbox / PyOneLibrary must stay on one thread for the
lifetime of a session.

## Decision

- Run the Textual app on **asyncio** (Textual's native loop).
- Run Rekordbox open and `sync_playlists` on a **dedicated executor
  thread**, not the default `asyncio.to_thread` pool.
- Run analysis tag writes on a small worker pool so crate work can
  continue on the Rekordbox thread.

There is no job registry, event bus, or persisted job record.

## Consequences

### Positive

- Single-process model simplifies PyInstaller packaging
- Rekordbox thread affinity stays correct across Library, Progress, and quit
- Progress callbacks stay ordinary Python callables

### Negative

- Care is required at the sync/async boundary
- Tests that touch rbox must not hop threads mid-handle

### Neutral

- Analysis workers are capped so a USB stick is not flooded
