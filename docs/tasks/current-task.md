# Current Task

**Status:** `complete`
**Task ID:** `TASK-312`
**Last updated:** 2026-08-30

## Objective

Grow a WAV ``id3 `` chunk that sits after ``data`` so a tight tag can
take new Serato frames without moving the audio stream.

## Files touched

- `app/adapters/serato/tags.py`
- `tests/test_audio_tags.py`
- `tests/test_audio_commit.py`
- `docs/workflows/audio-commit.md`
- `docs/adapters/serato.md`
- `docs/tasks/backlog.md`
- `docs/tasks/completed-tasks.md`
- `docs/HANDOFF.md`
- `docs/state/task-state.json`
- `docs/state/repository-state.json`
- `docs/state/architecture-state.json`

## Verification criteria

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

## Verification log

- ruff: pass
- ruff format: pass
- pytest: 362 passed / 4 skipped
