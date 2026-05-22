# ADR 0002: Use asyncio for Jobs

**Status:** accepted  
**Date:** 2026-05-22

## Context

Operations such as full USB scans and multi-file backups are I/O-bound and long-running. The CLI must remain responsive for progress output, cancellation, and future GUI attachment.

Alternatives: threaded pool only, synchronous blocking CLI, external worker process (Celery-style — overkill).

## Decision

Use **`asyncio`** as the job orchestration runtime:

- `JobRunner` schedules coroutine-based jobs
- Blocking adapter/storage I/O runs in `asyncio.to_thread`
- Progress via in-process event bus

## Consequences

### Positive

- Single-process model simplifies PyInstaller packaging
- Native async/await fits progress and cancel checkpoints
- No extra broker infrastructure

### Negative

- Care required at sync/async boundaries
- SQLite async requires thread pool or dedicated async driver
- Testing async code needs `pytest-asyncio`

### Neutral

- Job state persisted to JSON files on disk, not in-memory only
