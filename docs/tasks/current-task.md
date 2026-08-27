# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-220` |
| Objective | User: "well i dont see the verbose message of scanning usbs when the first screen shows. only the spinning circle" -- then, mid-implementation, refined to a specific fixed caption and asked for a more noticeable spinner ("is there a better spinner icon? its quite small") |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/screens/home.py`:
  - New `_SCANNING = "Automatically detecting for a DJ USB…"` constant.
    `_show_spinner()` now shows this (dim, not red -- routine "still
    looking" information, not a problem) alongside the spinner, instead
    of leaving the status line hidden and blank during ordinary
    searching. `_show_error()`'s red message path is unchanged.
  - `on_mount` now calls `self._show_spinner()` directly instead of
    separately hiding the status line and waiting for the first poll
    tick to populate it -- the caption is visible from the very first
    rendered frame.
  - `_SPINNER_FRAMES` changed from a rotating quarter-circle (`◐◓◑◒`) to
    a pulsing dot growing and shrinking (`· • ● •`), at a slightly slower
    tick (0.15s vs 0.1s) so each size is actually perceptible -- the
    user's own description of what they wanted ("i don't mind that
    pulsing dot approach"), and a direct response to "its quite small":
    a solid `●` at full pulse reads as noticeably bigger than a thin
    quarter-circle arc ever did.
  - Tried, then reverted before committing: a `describe_scan_locations()`
    helper (in `app/storage/mounts.py`, re-exported through
    `app/services/library.py` per the `tui` -> `storage` layer rule) that
    named the platform-specific scan location and the `USBVERSAL_MOUNT`
    override in the caption text. The user asked for the fixed, simpler
    wording above instead once they saw where this was headed, so the
    helper (and its test) were removed again rather than left unused --
    never shipped, so no entry above in "what changed" beyond this note.
- `tests/test_tui_home.py` -- `test_shows_searching_with_nothing_mounted`
  now asserts `status.display is True` and "Automatically detecting" in
  its text (previously asserted `display is False`, back when searching
  showed nothing at all).

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 273 passed, 4 skipped |
| Direct render inspection | Confirmed the status line reads exactly "Automatically detecting for a DJ USB…" and the spinner cycles `· → • → ● → • → ·` |
| Real terminal | **Not yet seen by the user.** Same as every other TUI change this session. |

## Next

Ask the user to confirm the Home screen shows the caption and a visibly
pulsing dot while searching, not a bare small spinner.

**The large pending Library screen redesign is still not started** -- see
[`docs/HANDOFF.md`](../HANDOFF.md)'s "Pending: Library screen redesign"
section for the full spec and the open question about settings
persistence. Also still outstanding: real-hardware re-confirmation of
TASK-210/211/212, the TASK-213/214 banner/spinner/colours, and the
TASK-216/217 mount-detection changes on real macOS/Windows/Linux-desktop
hardware.
