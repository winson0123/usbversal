# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-242` |
| Objective | Read and write Serato BeatGrid / Markers2 on FLAC via Vorbis comments |
| Completed | 2026-08-27 |

### Scope

- FLAC path in `tags.py`: `SERATO_BEATGRID` / `SERATO_MARKERS_V2`, base64 wrap, STREAMINFO + audio unchanged.
- Tests: round-trip, foreign comment, audio hash, named removal.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 276 passed, 4 skipped |

## Next

Ask the user.
