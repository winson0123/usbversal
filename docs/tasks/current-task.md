# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-208` |
| Objective | Screens 4-5 of the target flow (Progress, Done), and the point `sync_playlists()` first becomes reachable from the TUI at all |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/services/sync_service.py` — `_sync_analysis` and `sync_playlists` gained
  an optional `on_progress: Callable[[int, int], None] | None` parameter,
  called once per track in the analysis pass (the slow, per-track part of a
  sync); not called at all for a dry run or when nothing has analysis data
- `app/jobs/progress_rate.py` — `format_duration()` extracted from
  `app/cli/progress.py` (was module-private there) to a shared public
  function, so the CLI and the new TUI screen format an ETA the same way
- `app/cli/progress.py` — updated to import `format_duration` instead of
  keeping its own copy
- `app/tui/screens/progress.py` (new) — `ProgressScreen` runs `sync_playlists`
  via `asyncio.to_thread` inside a worker, marshals `on_progress` callbacks
  back to the UI thread with `self.app.call_from_thread`, and renders a
  `textual.widgets.ProgressBar` plus rate/ETA text from
  `ProgressRateTracker`; `DoneScreen` shows a completion (or failure)
  summary, enter returns to whatever screen was open before the sync
  (`switch_screen` on the Progress → Done transition keeps Library
  underneath rather than stacking), escape quits
- `app/tui/screens/library.py` — enter with a non-empty selection now pushes
  `ProgressScreen` instead of only reporting the count
- `tests/test_sync_playlists.py` — two new tests for `on_progress`: fires once
  per analysis track, and not at all when nothing has analysis data
- `tests/test_progress_rate.py` — two new tests for `format_duration`
- `tests/test_tui_progress.py` (new) — five tests: progress samples reach the
  bar and the run transitions to Done, a raised exception is caught and shown
  rather than crashing the app, analysis errors are called out in the
  summary, enter on Done returns to the screen that was open before Progress
  (not just "pop once"), and `_update_progress` sets the bar's `total`/`progress`
  correctly (called directly — see below)
- `tests/test_tui_library.py` — the enter-confirms test split into two: no
  selection doesn't start a sync, a selection hands off to Progress with the
  right library and ids (both patch `ProgressScreen` with a dummy, matching
  the same isolation pattern `test_tui_home.py` already used for `LibraryScreen`)
- `docs/planning/interactive-tui.md`, `README.md`, `docs/tasks/backlog.md`,
  `docs/state/*.json`

### Design decisions

- **Progress is per analysis-track only, not the whole run.** Instrumenting
  `append_database_tracks` and the per-playlist crate-write loop as well
  would need changes to `writer.py` too, for comparatively fast, mostly-batch
  operations. The analysis pass is what HANDOFF.md and TASK-110 already
  identify as the slow part, so that's what a progress bar should track;
  said so explicitly in `known_gaps`.
- **Progress → Done uses `switch_screen`, not `push_screen`.** Pushing would
  leave `[..., Library, Progress, Done]` on the stack, and "enter returns to
  Library" would need popping twice. Replacing Progress with Done via
  `switch_screen` keeps `[..., Library, Done]`, so returning is one
  `pop_screen()` regardless of what was open before Progress was pushed —
  verified with a marker screen standing in for "whatever was there,"
  not hardcoded to assume it was Library specifically.
- **`on_progress` is called from a worker thread; `call_from_thread` marshals
  it back.** `sync_playlists` runs via `asyncio.to_thread`, so its callback
  fires on that thread, not the event loop's. Touching Textual widgets
  directly from there would be unsafe; `self.app.call_from_thread(...)` is
  the mechanism Textual provides for exactly this.
- **One test calls `_update_progress` directly rather than through the real
  worker.** The faked `sync_playlists` is synchronous and effectively
  instant, so there was no reliable window between "Progress screen mounted"
  and "already switched to Done" to catch the live `ProgressBar` mid-update —
  confirmed by two failed timing-based attempts before settling on calling
  the method directly. Noted as a comment in the test so a future reader
  doesn't reintroduce the same race trying to make the test "more real."
- **`format_duration` is genuinely shared**, not merely duplicated between
  CLI and TUI. The alternative (leaving `app/cli/progress.py`'s copy in
  place and writing a second one for the TUI) would have both formats drift
  the first time someone changed one, especially since neither is directly
  tested for that specific coupling.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 219 passed, 4 skipped (no stick mounted, no `dist/usbversal` built; skips are 2 `/mnt/usb` integration tests, the opt-in full PyInstaller build, and the binary-help smoke test) |
| `.venv/bin/python -m app.cli --help` | unchanged |
| Manual end-to-end smoke (not committed, source-level, throwaway script) | Home → poll → Library → space-select → enter → Progress → (patched `sync_playlists`) → Done → enter → back to Library, all real screens chained together (no dummy substitutes), confirmed working |

## Next

M11 (Interactive TUI) is now fully built — TASK-200 through TASK-208 are all
done. `docs/tasks/backlog.md` next has `TASK-075` (nested playlist folder
naming) and `TASK-076` (bootstrap `_Serato_` on a rekordbox-only stick), both
older M8 items; `TASK-090` (`export.pdb` reader) is explicitly deferred/lower
priority. `TASK-075` and `TASK-090` both note they need a real stick to
validate the naming convention / dump results against, which is not mounted
this session.
