# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-212` |
| Objective | Fix a new user-reported crash on TUI exit: `RuntimeError: _rbox::one_library::PyOneLibrary is unsendable, but is being dropped on another thread` |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/app.py`:
  - `UsbversalApp.action_quit` (new, async override): before handing off
    to Textual's own `action_quit`, walks `self.screen_stack` and nulls out
    every screen's `library`/`_library` attribute inside one call pinned to
    the dedicated rekordbox thread (`run_rekordbox`), then runs `gc.collect()`
    on that same thread.
  - `RekordboxThreadMixin._shutdown_rekordbox_thread`: `shutdown(wait=False)`
    -> `shutdown(wait=True)`, now that nothing is left in flight by the time
    it's called.
- `tests/test_tui_app.py` — new test pushes two fake screens holding
  `library`/`_library` references, calls `action_quit()`, and asserts both
  are `None` afterward.
- `docs/tasks/backlog.md`, `docs/state/*.json`

### Root cause

TASK-209 fixed the crash pyo3 raises when `PyOneLibrary` (the rbox binding
for Rekordbox's One Library format) is *used* from a thread other than the
one that created it, by pinning every `UsbLibrary.rekordbox` call through
`run_rekordbox`. This is a *different* manifestation of the same underlying
rule: pyo3 enforces thread affinity on **drop**, not just on use, and a
Python object's `__del__`/finalizer runs on whichever thread's refcount
decrement happens to hit zero -- not necessarily the thread that created it.

`HomeScreen.library`, `LibraryScreen._library`, and `ProgressScreen._library`
all hold references to the same opened `UsbLibrary` (and, inside it, the
`OneLibrary` object created on the dedicated thread via `open_library`).
During normal navigation this is harmless -- earlier screens stay on the
stack, so no reference count reaches zero. On quit, though, Textual tears
down the *entire* screen stack from the main thread, and whichever screen
happens to hold the last live reference is what actually triggers the
Rust-side Drop -- on the main thread, which pyo3 rejects.

### Fix

Rather than trying to guarantee teardown order across three independent
screens, `action_quit` now explicitly nulls every screen's reference to the
library *before* Textual's own teardown runs, and does so inside a single
function executed on the dedicated rekordbox thread. Whichever of those
`None` assignments turns out to be the one that drops the object's last
reference, it now runs in the right place. By the time Textual's normal
screen-stack unmounting happens afterward, there is nothing rekordbox-shaped
left for it to drop.

### Design decisions

- **Clear references explicitly rather than reordering/holding a single
  owner.** Restructuring `HomeScreen`/`LibraryScreen`/`ProgressScreen` to
  share one canonical owner (e.g. only the App holds the "real" reference,
  screens borrow it) wouldn't remove the problem -- Python doesn't let you
  pick which thread performs a refcount-triggered deallocation; it only
  moves which specific attribute clear is the deciding one. Explicitly
  walking the stack and nulling every known reference, inside one call
  pinned to the dedicated thread, handles this regardless of which
  screen(s) happen to hold the last live reference.
- **`shutdown(wait=True)` instead of `wait=False`.** With the cleanup
  awaited before this call, there's no in-flight work left to cut off, so
  there's no reason not to actually join the thread.
- **Generic `hasattr` scan over `library`/`_library`, not per-screen-class
  code.** `HomeScreen` uses `library` (public, so Home's own logic can
  check it after re-entering Home); `LibraryScreen`/`ProgressScreen` use
  `_library`. A small closed set of attribute names covers every screen
  that will ever hold this reference without hardcoding per-class handling
  that would need updating every time a new screen is added.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 249 passed, 4 skipped (no stick mounted in this environment, no `dist/usbversal` built) |
| New test | `test_quit_clears_library_references_on_the_rekordbox_thread` — pushes two fake screens holding `library`/`_library` references, calls `action_quit()`, asserts both are cleared |
| Real hardware | **Not yet re-confirmed by the user.** This crash (unlike TASK-209's) never reproduced in this environment at all -- the TUI test suite mocks/fakes the rekordbox adapter, which has no thread affinity to violate. The fix follows directly from pyo3's documented drop-thread-affinity rule and mirrors the same fix shape TASK-209 already used and the user already confirmed works for *access*; it has not been run against a real `PyOneLibrary` object. |

## Next

Ask the user to re-run against `/mnt/usb` and confirm the app exits cleanly
(no `RuntimeError`/abort on quit), and -- since they haven't yet confirmed
TASK-210/211 either -- also check that the Library screen's columns line up,
that "All playlists" is collapsible, and that returning to Library after a
sync shows the correct synced/total counts without needing a restart.
