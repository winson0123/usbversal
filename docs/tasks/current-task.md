# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-241` |
| Objective | Confirm ID3v2.4 MP3 GEOB write/read; keep the v2.3 size branch honest |
| Completed | 2026-08-27 |

### Scope

- Added `tests/test_mp3_tags.py`: v2.4 synchsafe and v2.3 raw-size MP3 round-trips for BeatGrid and Markers2; audio after the tag unchanged.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 271 passed, 4 skipped |

## Next

Ask the user.
