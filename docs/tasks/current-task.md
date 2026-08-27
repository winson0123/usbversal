# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-240` |
| Objective | Remove the argparse CLI; `usbversal` launches the TUI |
| Completed | 2026-08-27 |

### Scope

- Deleted `app/cli/` and CLI-only tests.
- Entry point is `app.tui.app:run`; packaging spec points at `app/tui/__main__.py`.
- Layer rules no longer mention `cli`.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 269 passed, 4 skipped |

## Next

Ask the user.
