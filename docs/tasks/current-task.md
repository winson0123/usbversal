# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-28

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-250` |
| Objective | Run `correct_index_bpm` on WONSIN |
| Completed | 2026-08-28 |

### Scope

- Dry-run then live write of `location.sqlite` (7 rows).
- Host backup `20260828T072224Z`.
- Findings in `docs/workflows/index-bpm-wonsin.md`.

### Verification log

| Check | Result |
|-------|--------|
| Dry-run | 1286 candidates, 7 would update |
| Live write | 7 rows, backup `20260828T072224Z` |
| Dry-run after | 0 remaining |
| `.venv/bin/pytest` | 285 passed, 4 skipped (docs-only task) |

## Next

`TASK-251` — confirm Apt X Blue's 4-marker grid in Serato. Then Library two-pane.
