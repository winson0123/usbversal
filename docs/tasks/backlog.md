# Task Backlog

Queued work. **Only one task may be active** — see [`AGENT.md`](../../AGENT.md).

Priority order (top first). Decompose before starting if scope exceeds one commit.

---

## M1 — Project Foundation

| ID | Title | Notes |
|----|-------|-------|
| `TASK-001` | Add `pyproject.toml` and package skeleton | `app/`, no business logic |
| `TASK-002` | Configure ruff, pytest, dev dependencies | CI-ready |
| `TASK-003` | CLI entrypoint stub (`--help` only) | Thin layer |

## M2 — Storage Layer

| ID | Title | Notes |
|----|-------|-------|
| `TASK-010` | Mount path validation utilities | No auto-detect yet |
| `TASK-011` | Backup copy + manifest.json | See `docs/storage/backup-strategy.md` |
| `TASK-012` | Rollback from manifest | See `docs/storage/rollback-flow.md` |

## M3 — Core Domain

| ID | Title | Notes |
|----|-------|-------|
| `TASK-020` | Domain models (Library, Playlist, Track) | Dataclasses |
| `TASK-021` | Adapter protocol + WriteContext | Enforce backup_path |
| `TASK-022` | Event types and bus skeleton | |

## M4 — Adapters

| ID | Title | Notes |
|----|-------|-------|
| `TASK-030` | Rekordbox detect + read-only list | Fixture tests |
| `TASK-031` | Serato detect stub | Read-only, defensive parse |
| `TASK-032` | Rekordbox write path | Requires backup integration |

## M5 — Jobs

| ID | Title | Notes |
|----|-------|-------|
| `TASK-040` | JobRunner + registry | asyncio |
| `TASK-041` | Scan job | Emits progress events |
| `TASK-042` | Cancel + resume metadata | |

## M6 — CLI Commands

| ID | Title | Notes |
|----|-------|-------|
| `TASK-050` | `scan` command | Delegates to scan job |
| `TASK-051` | `list-playlists` / `list-crates` | |
| `TASK-052` | `backup` / `rollback` | |
| `TASK-053` | `apply` with plan file | |

## M7 — Packaging & Validation

| ID | Title | Notes |
|----|-------|-------|
| `TASK-060` | PyInstaller spec + smoke test | ADR 0003 |
| `TASK-061` | `/mnt/usb` integration validation | Manual + documented |
