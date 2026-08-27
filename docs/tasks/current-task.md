# Current Task

**Status:** `complete`
**Task ID:** TASK-227
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-227` |
| Objective | Replace Home's `_seen_invalid` flag pile with an explicit `HomePhase` |
| Completed | 2026-08-27 |

### Scope

- `app/tui/screens/home.py`: `SEARCHING | FAILED | OPENING | READY`. `poll_mounts` only transitions. `_show_phase` (not `_render` — that name is Textual's) paints widgets on change. Timeout only applies while `SEARCHING`. Hidden path input stays disabled (Textual focus rule).
- `tests/test_tui_home.py`: `_force_error_state` / `_seen_invalid` retargeted to `_enter` / `HomePhase`. Under-timeout fixture is `SCAN_TIMEOUT_S - 0.5`.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 278 passed, 4 skipped |

## Next

TASK-228 — Extract PathInput to `app/tui/widgets/path_input.py`.
