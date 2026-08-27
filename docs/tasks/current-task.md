# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-222` |
| Objective | User: "now stuck on the screen? when usb not plugged in, should have retry/timeout" |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/screens/home.py`:
  - `HomeScreen.SCAN_TIMEOUT_S = 15.0` (new class attribute, alongside
    the existing `POLL_INTERVAL_S`).
  - `self._searching_since = time.monotonic()`, set once in `__init__`.
  - `poll_mounts()`: after the existing appeared/rejected loop, if
    `_seen_invalid` is still `False` but `SCAN_TIMEOUT_S` has elapsed
    since `_searching_since`, set `_seen_invalid = True` anyway. From
    there it falls into the exact same `_show_error(_NONE_FOUND)` branch
    a real rejection already used -- no second message, no second state
    to keep in sync with the first.
  - Class docstring updated to describe this: nothing plugged in at all
    now behaves identically to something invalid being found, once the
    timeout passes.
- `tests/test_tui_home.py` -- two new tests, both driving the timeout by
  setting `home._searching_since` into the past rather than sleeping:
  `test_still_within_the_timeout_keeps_spinning` (well under the
  threshold, still spinner + hidden input) and
  `test_search_times_out_and_reveals_manual_entry` (past the threshold,
  spinner hidden, red `_NONE_FOUND` message, input visible/enabled).

### Root cause

`poll_mounts()`'s only path to `_seen_invalid = True` was "a mount
appeared and got rejected." Nothing ever appearing at all -- no stick
plugged in, or `USBVERSAL_MOUNT` unset and no platform auto-mount --
never took that branch, so the screen stayed in the quiet-searching state
(spinner + dim caption) indefinitely, with the manual-path input staying
hidden the entire time. There was no path out of that state without
plugging something in.

### Design decisions

- **Reused `_seen_invalid` and `_NONE_FOUND` rather than adding a
  distinct "timed out" state.** "Did not detect a valid DJ USB" is
  equally true whether the cause was a rejected mount or nothing showing
  up at all, and the UI response (reveal the input, stop assuming
  something will still turn up) is identical either way -- a second
  parallel flag/message would only be able to drift from the first, not
  add anything a user needs to see differently.
- **15 seconds, not shorter.** Long enough that a real stick's OS-level
  auto-mount (which can itself take a couple of seconds) has clearly had
  its chance before giving up, short enough that a user who genuinely has
  nothing plugged in isn't left watching a bare spinner for an
  uncomfortably long stretch.
- **Tests set `_searching_since` into the past instead of sleeping.**
  15 real seconds per test (times however many) would make the suite
  noticeably slower for no benefit -- the thing under test is the
  comparison against `time.monotonic()`, not real wall-clock delay.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 275 passed, 4 skipped (2 new) |
| Direct state inspection | Confirmed: just before the timeout, spinner shown and input hidden; just past it, spinner hidden, status reads "Did not detect a valid DJ USB", and the input is visible, enabled, and focused |
| Real terminal | **Not yet seen by the user.** Same as every other TUI change this session. |

## Next

Ask the user to confirm: with nothing plugged in, the Home screen now
gives up after ~15 seconds and offers the manual-path input, instead of
spinning forever.

**The large pending Library screen redesign is still not started** -- see
[`docs/HANDOFF.md`](../HANDOFF.md)'s "Pending: Library screen redesign"
section for the full spec and the open question about settings
persistence. Also still outstanding: real-hardware re-confirmation of
TASK-210/211/212, the TASK-213/214 banner/colours, and the TASK-216/217
mount-detection changes on real macOS/Windows/Linux-desktop hardware.
