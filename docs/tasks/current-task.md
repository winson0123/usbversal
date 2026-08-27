# Current Task

**Status:** `complete`
**Task ID:** TASK-226
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-226` |
| Objective | Move TUI session-open (bootstrap + open + readability check) into `prepare_library` |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/services/library.py`: new `prepare_library(mount)` — bootstrap Serato if needed, `open_library`, then `list_playlists()` so a database that opens but cannot be read fails before the Library screen takes over. `open_library` itself is unchanged (CLI must not create `_Serato_`).
- `app/tui/screens/home.py`: `_open` is one `run_rekordbox(prepare_library, mount)` call.
- `tests/test_tui_home.py`: retargeted dual bootstrap/open patches to `prepare_library`. The real-bootstrap test still runs unpatched bootstrap by patching `open_library` on the service module.
- `tests/test_library.py`: contract test that prepare bootstraps then opens.

The discarded `list_playlists()` call on Home originally displayed "Ready: N playlists" (TASK-206). That UI is gone, but Home still catches a failed read before push — kept as the readability check inside `prepare_library`.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 278 passed, 4 skipped |

## Next

TASK-227 — Home phase machine (`HomePhase` instead of `_seen_invalid`).
