# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-232` |
| Objective | Quit restores the terminal immediately; Rekordbox Drop waits until after the UI is gone |
| Completed | 2026-08-27 |

### Scope

- `app/tui/app.py`: `q` parks each screen's `library` on the app (re-point only) and `exit()`s. `on_unmount` Drops the parked handles on the rekordbox thread after Textual has left the alt screen.
- `tests/test_tui_app.py`: park-without-drop, Drop-on-rekordbox-thread, and no-hop-from-Home.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 279 passed, 4 skipped |

## Next

Ask the user. The large pending Library screen redesign is still not started — see `docs/HANDOFF.md`.
