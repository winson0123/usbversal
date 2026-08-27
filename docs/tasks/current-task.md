# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-219` |
| Objective | User: "need verbose, i dont know what is happening on progress bar. green verbose, red on error" |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/services/sync_service.py`:
  - New `SyncProgressCallback = Callable[[int, int, str, str | None], None]`
    type alias, used by both `_sync_analysis` and `sync_playlists`.
  - `_sync_analysis`'s per-track loop now captures a `track_error: str |
    None` local per iteration (set in the existing `except` branch instead
    of only being appended to the function-level `errors` list) and passes
    it, plus the track's own path (`raw`), to `on_progress` on every call.
    Callers that only care about counts can still ignore the new
    arguments; nothing about the done/total semantics changed.
- `app/tui/screens/progress.py`:
  - `ProgressScreen` gained a `RichLog` (`max_lines=500`) under the
    existing status line and `ProgressBar`. `_update_progress` (and the
    `_report_progress` thread-marshalling wrapper) now take `(done, total,
    track, error)` and write one line per track: green on success, red
    with the error message on failure.
  - A top-level sync failure (an exception from `sync_playlists` itself,
    not a single track) also gets a red line in the log before switching
    to `DoneScreen`.
  - `DoneScreen._summary()` now returns a `rich.text.Text` (not a plain
    `str`) styled green when nothing failed, red when there's a hard
    error or any `analysis_errors`.
  - **Both use `Text(..., style=...)` rather than markup strings**
    (`f"[red]{message}[/red]"`). A track path or exception message is
    arbitrary data and could itself contain `[...]`, which markup parsing
    would misread as a tag and corrupt the line. Found and fixed the same
    pre-existing pattern in `HomeScreen._show_error` while touching
    adjacent code in this same task.
- `app/tui/app.py` -- `RichLog` added to the app-level CSS neutralization
  block alongside `Footer`/`Tree` (TASK-214): its own `DEFAULT_CSS` has no
  `:ansi` rule at all, so both `background` and `color` defaulted to a
  themed near-black/light-grey regardless of `ansi_color=True`. Confirmed
  the explicit per-line green/red styles still take precedence over the
  neutralized base style.
- `tests/test_sync_playlists.py`, `tests/test_tui_progress.py` -- updated
  every `on_progress` caller/fake for the new 4-argument signature; six
  new tests (a failing-track case for the sync-level callback; two
  `RichLog` line/colour checks read back via `log.lines[i]`'s segment
  styles; three `DoneScreen` colour checks read back via
  `Static.render().spans`).

### Design decisions

- **Extended the existing callback rather than adding a second one.**
  `on_progress` was already the one hook `sync_playlists` offers a caller
  driving a progress bar; adding `track`/`error` to it kept there being
  exactly one thing to wire up, instead of a second parallel "verbose
  events" channel that could drift out of step with the counts.
- **Did not fabricate progress for the crate-write/record-add steps.**
  Those still have no instrumentation at all (a pre-existing, separately
  tracked gap -- see `known_gaps`); inventing synthetic log lines for
  steps this project has no real per-item data for would have been
  misleading verbosity, not real information.
- **`rich.text.Text`, not markup, for anything embedding arbitrary
  strings.** This surfaced as a real bug candidate while implementing the
  log lines (a track path with a literal `[` would have broken a markup
  string), not a hypothetical -- worth the small extra care everywhere
  user-controlled or exception text meets a coloured line.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 273 passed, 4 skipped (6 new) |
| Direct `RichLog.lines`/`Static.render()` inspection | Confirmed a green line's segment style resolves to `Color('green', ...)`, a red line's to `Color('red', ...)`, and `DoneScreen`'s rendered `Content` carries a `Span(..., style='green')` or `'red')` matching whether anything failed |
| Real terminal | **Not yet seen by the user.** Same as every other TUI change this session -- verified only via `Pilot`/direct widget inspection here. |

## Next

**A large new feature request came in and was deliberately deferred, not
started** -- see [`docs/HANDOFF.md`](../HANDOFF.md)'s "Pending: Library
screen redesign" section for the full spec, an open question about how
metadata-column preferences should persist, and a suggested breakdown into
several ordered sub-tasks. Read that before starting the next piece of
work on this screen.

Also still outstanding from earlier tasks: real-hardware re-confirmation
of TASK-210/211/212, the TASK-213/214 banner/spinner/colours, and the
TASK-216/217 mount-detection changes on real macOS/Windows/Linux-desktop
hardware.
