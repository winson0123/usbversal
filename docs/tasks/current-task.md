# Current task

**Status:** `complete`
**Task ID:** `TASK-327`
**Last updated:** 2026-09-01

## Objective

Replace first-person narrator in repo docs with the project name or a direct statement.

## Files touched

- `README.md`
- `AGENT.md`
- `ARCHITECTURE.md`
- `docs/decisions/0001-use-python.md`
- `docs/decisions/0002-use-asyncio.md`
- `docs/decisions/0003-use-pyinstaller.md`
- `docs/decisions/0004-use-rbox-rekordbox-reader.md`
- `docs/decisions/0005-use-serato-tools.md`
- `docs/decisions/0008-beatgrid-and-cue-sync-validated-in-serato.md`
- `docs/decisions/0009-use-textual-for-the-tui.md`
- `docs/decisions/0010-tolerate-leftover-markers2-base64.md`
- `docs/adapters/rekordbox.md`
- `docs/adapters/serato.md`
- `docs/schemas/rekordbox-schema-notes.md`
- `docs/schemas/serato-schema-notes.md`
- `docs/workflows/audio-commit.md`
- `docs/workflows/m4a-markers.md`
- `docs/state/task-state.json`
- `docs/state/repository-state.json`
- `docs/tasks/current-task.md`
- `docs/tasks/backlog.md`

## Verification

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

- ruff check: pass
- ruff format: pass
- pytest: 332 passed, 3 skipped
