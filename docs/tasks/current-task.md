# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-215` |
| Objective | User asked: insert a valid USB and press enter to retry scanning, optionally type the path directly, with Tab completion |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/screens/home.py`:
  - `_complete_path(partial) -> str \| None` -- shell-style Tab completion.
    Splits the partial into a directory and a name prefix, lists matching
    entries, and completes to their longest common prefix
    (`os.path.commonprefix`); returns `None` (no-op) when there's nothing
    new to add (no matches, or the common prefix among several matches
    equals what's already typed) so repeated Tab presses on an already-
    maximal, still-ambiguous prefix do nothing rather than erroring. A
    single unambiguous directory match gets a trailing `/`, matching
    ordinary shell completion.
  - `_PathInput(Input)` -- a `tab` binding (non-priority) calling
    `action_complete`, which applies `_complete_path` to the current
    value. Textual checks a *focused* widget's own bindings before
    walking up to `Screen`'s (which has its own default `tab` ->
    `app.focus_next`), so this didn't need `priority=True` the way
    TASK-207's space-vs-Tree binding conflict did -- confirmed by
    pressing Tab through a real `Pilot` and reading the value back,
    not just calling the action method directly.
  - `HomeScreen`: `_PathInput` sits in its own `Center` under the
    spinner/status slot, auto-focused in `on_mount`. `on_input_submitted`
    handles `Input.Submitted`: an empty value calls `self.poll_mounts()`
    immediately (retry now, instead of waiting up to `POLL_INTERVAL_S`
    for the next timer tick); a non-empty value goes straight to
    `self._open(Path(value))`, the same bootstrap/open/hand-off path a
    watcher-discovered mount already uses. `_open` now disables the
    input while a real attempt is in flight and re-enables it (with
    focus restored) on failure, so a bad manually typed path doesn't
    leave the field stuck.
- `tests/test_tui_home.py` -- 7 new tests: three direct unit tests of
  `_complete_path` (fills a common prefix, adds a trailing slash for a
  unique directory, no-ops on no-match/already-maximal-ambiguous), and
  four `Pilot`-driven ones (Tab actually completes the focused input,
  Enter on empty input retries immediately, Enter with a typed path opens
  it and hands off to Library, a failed manual path re-enables the input).

### Design decisions

- **Retry reuses `poll_mounts()` rather than a separate code path.**
  `poll_mounts()` already does the right thing when called at an arbitrary
  moment -- diffs the watcher, opens a newly valid mount if one showed up,
  otherwise falls back to the spinner/error state exactly as before -- so
  "retry now" is just "call the same function early" rather than new logic
  with its own risk of drifting from what the timer-driven path does.
- **Manual path entry reuses `_open()` rather than duplicating its
  probe/bootstrap/open/error-handling.** The only new thing a manually
  typed path needs is *not* going through `probe_mount` first (the user
  is asserting this path directly, rather than it being auto-discovered);
  everything after that -- bootstrap, open, the same exception handling,
  the same push to `LibraryScreen` -- is identical, so it was cheaper and
  safer to call the existing method than fork it.
- **No validation before calling `_open()` on a typed path.** `_open`
  already catches `OSError` (covers a nonexistent/non-directory path),
  `DatabaseNotFoundError`, and `UnsupportedDatabaseError` and turns each
  into the same red error message auto-detection uses -- adding a second,
  earlier validation step would just be two places that could disagree
  about what counts as a valid path.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 256 passed, 4 skipped (7 new) |
| Manual `Pilot` check | Typed a partial path into the real input, pressed Tab through `pilot.press`, and confirmed the value completed and focus stayed on the input, before writing the equivalent test |
| Real terminal | **Not yet seen by the user.** Verified only through `Pilot`/unit tests in this environment, same as TASK-213/214. |

## Next

Ask the user to try this against a real terminal: confirm the input field
is focused and usable on launch, that pressing Enter with a stick freshly
inserted actually retries without waiting, that typing a path and pressing
Enter opens it, and that Tab completion behaves sensibly against their
actual mount paths (e.g. `/media/<user>/...` or `/mnt/...`). Also still
outstanding: real-hardware re-confirmation of TASK-210/211/212's fixes and
how the TASK-213/214 banner/spinner/colours actually look in their
terminal.
