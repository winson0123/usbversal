# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-233` |
| Objective | Skip the alternate screen on ConPTY so quit is not blocked by Windows Terminal's ~1s buffer swap |
| Completed | 2026-08-27 |

### Scope

- `app/tui/app.py`: on WSL / Windows Terminal, replace `CSI ? 1049 h/l` with a viewport clear so we never enter the alt screen. Other terminals keep it.
- `tests/test_tui_app.py`: rewrite, host detect, and write-filter coverage.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 284 passed, 4 skipped |

## Next

Ask the user. The large pending Library screen redesign is still not started — see `docs/HANDOFF.md`.
