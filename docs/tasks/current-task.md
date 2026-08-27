# Current Task

**Status:** `complete`
**Task ID:** TASK-228
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-228` |
| Objective | Move PathInput + match_candidates out of the Home screen module |
| Completed | 2026-08-27 |

### Scope

- `app/tui/widgets/path_input.py`: Tab-cycle path field.
- `app/tui/screens/home.py`: imports `PathInput`; scan bar stays here.
- `tests/test_tui_home.py`: import path retarget only.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 278 passed, 4 skipped |

## Next

TASK-229 — Unify `library` attribute on Home/Library/Progress; simplify quit clearing.
