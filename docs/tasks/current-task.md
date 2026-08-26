# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-209` |
| Objective | Fix a real process-abort the TUI hit on its first run against actual hardware — a crash no test in this codebase could have caught |
| Completed | 2026-08-27 |

### Scope

The user ran `usbversal tui` against a real `/mnt/usb` stick and hit:

```
thread '<unnamed>' panicked: assertion 'left == right' failed:
_rbox::one_library::PyOneLibrary is unsendable, but sent to another thread
```

`rbox`'s `PyOneLibrary` (the pyo3-wrapped Rust type backing
`UsbLibrary.rekordbox`) is not `Send` — pyo3 aborts the whole process, not
just raises a Python exception, the moment it is touched from any thread but
the one that created it. Every TUI screen from TASK-206 onward wrapped
blocking Rekordbox reads in `asyncio.to_thread`, whose shared default
executor does not guarantee the same worker thread across separate calls —
`HomeScreen._open` alone crossed threads twice (`open_library` on one
executor thread, then `list_playlists()` back on the main thread the instant
the `await` returned).

Files touched:

- `app/tui/app.py` — `RekordboxThreadMixin`: a single-worker `ThreadPoolExecutor`
  kept for the app's whole lifetime, with `run_rekordbox(func, *args, **kwargs)`
  marshalling any blocking call onto it via `functools.partial` +
  `loop.run_in_executor`. `UsbversalApp` mixes it in (`RekordboxThreadMixin, App`)
  rather than defining its own executor inline.
- `app/tui/screens/home.py` — `open_library` and the `list_playlists()` count
  both now go through `self.app.run_rekordbox(...)`; `bootstrap_serato_library`
  stays on plain `asyncio.to_thread` since it never touches `library.rekordbox`
- `app/tui/screens/library.py` — `on_mount` is now `async def` and awaits
  `self.app.run_rekordbox(playlist_tree_sync_states, self._library)`
- `app/tui/screens/progress.py` — `_run` awaits
  `self.app.run_rekordbox(sync_playlists, ...)` instead of `asyncio.to_thread`
- `tests/test_tui_app.py` (new) — four tests: two `run_rekordbox` calls land
  on the identical OS thread, that thread is not the event-loop thread,
  positional/keyword arguments reach the wrapped callable intact, and
  `UsbversalApp` pushes exactly one Home screen (guards the MRO gotcha below)
- `tests/test_tui_home.py`, `tests/test_tui_library.py`, `tests/test_tui_progress.py`
  — their throwaway test harnesses (`_Harness`, `_LibraryHarness`) now mix
  `RekordboxThreadMixin` into a bare `App` instead of subclassing `UsbversalApp`

### A second bug found getting the fix right

Subclassing `UsbversalApp` in a test harness and overriding `on_mount` to
push a different starting screen seemed like the obvious way to reuse
`run_rekordbox` in tests. It silently pushed **both** screens — `HomeScreen`
ended up on top regardless of what the harness intended. Textual dispatches
lifecycle messages like `on_mount` to *every* class in the MRO that defines
one, not just the most-derived override (confirmed with a minimal two-class
repro outside this codebase before touching anything real). Fixed by giving
`RekordboxThreadMixin` no `on_mount` of its own and mixing it directly into a
bare `App` in every test harness, so only one class in each hierarchy ever
defines the handler.

### Why no test caught the original crash

Every existing TUI test drives `library.rekordbox` through a `MagicMock` or
a real-but-synthetic `UsbLibrary` built from test fixtures — neither has any
thread affinity to violate, so the whole test suite passed while the real
thing aborted the process on first contact with actual hardware. Recorded
explicitly in `known_gaps`: this class of bug is only found by running
against a real stick, which is exactly what happened here.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 239 passed, 4 skipped (no stick mounted in this environment, no `dist/usbversal` built) |
| `.venv/bin/python -m app.cli --help` | unchanged |
| Real hardware | **Not re-verified by this agent** — no stick is mounted in this environment. The fix is reasoned from the exact panic message and the pyo3/rbox thread-affinity contract, and covered by `test_tui_app.py`'s thread-identity tests, but the user's own re-run against `/mnt/usb` is the check that actually closes the loop. |

## Next

Ask the user to re-run `usbversal tui` (or `python -m app.tui`) against the
real stick and confirm the crash is gone. If it opens cleanly and the
Library screen renders, the fix holds; if anything else surfaces, it's
almost certainly another real-hardware-only issue this session's mocked
tests structurally cannot see coming.
