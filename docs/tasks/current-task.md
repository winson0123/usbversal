# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-29

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-263` |
| Objective | `read_geob` / `write_geob` for AIFF / AIF and M4A / MP4 |
| Completed | 2026-08-29 |

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 331 passed, 4 skipped |

## Next

`TASK-277` — skip `write_geob` when the intended BeatGrid/Markers2 bytes are already on the file. Same track in two playlists in one run is already unique; this is the re-sync waste. Then `TASK-252` (library two-pane, last).
