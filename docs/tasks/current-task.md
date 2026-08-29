# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-29

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-272` |
| Objective | Read and write Serato frames on ID3v2.2 MP3s (`GEO`, 6-byte headers) |
| Completed | 2026-08-29 |

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 309 passed, 4 skipped |

Replayed BeatGrid write on the two WONSIN `20260829T075133Z` delta heads (dummy audio). Both read back; Overview kept; Humble still has `Offsets_` and did not need to grow.

## Next

`TASK-263` — AIFF / AIF Serato tags.
