# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-221` |
| Objective | User asked to replace TASK-220's single pulsing dot with a `[···••●]`-style bar sweeping left to right, then refined the fill and width twice more in the same sitting |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/screens/home.py`:
  - `_scan_bar_frame(head: int) -> str` (new, module-level) -- renders a
    fixed-width bar with `●` at the head position, `•` one cell behind
    it, and `·` everywhere else (both the run ahead of the head not yet
    reached, and the trail behind it once it's faded past one step).
    `_BAR_WIDTH = 4` (started at 8, narrowed to 6 on request to match the
    width of the user's own example, then the user edited it down to 4
    directly).
  - `_Spinner.on_mount`/`_tick` now call `_scan_bar_frame` instead of
    indexing a fixed frame tuple; frame count is `_BAR_WIDTH + 2` (one
    full sweep across, plus the two extra frames needed for the trailing
    `•` to clear before the head re-enters at position 0).
  - `_Spinner`'s id (`#spinner`), CSS, and mount lifecycle are unchanged
    -- only what it renders each tick changed, so nothing downstream
    (`_show_spinner`/`_show_error`'s show/hide toggling, the layout CSS)
    needed touching.

### Sequence within this task

Landed in three small refinements against the same feature, in direct
response to the user watching it and reacting:

1. First cut: bright point sweeping over a *blank* background --
   `[  ·•●   ]`-style, empty space everywhere the trail hadn't reached.
2. User: "i want the blank space to be the smallest dot" -- resting fill
   changed from `" "` to `"·"`, so untouched cells read as the same
   smallest dot the trail fades into rather than a gap.
3. User: "smaller in width?" -- `_BAR_WIDTH` 8 -> 6.
4. User edited `_BAR_WIDTH` to 4 directly ("i changed it to 4") -- left
   as is; the comment's inline example was the only thing that needed
   fixing to match (was still showing the width-6 shape).

No test changes were needed at any point -- the existing TUI test suite
never asserted on the spinner's exact rendered characters, only on
`display`/visibility toggling, which this never touched.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 273 passed, 4 skipped (unchanged count -- no test touched this) |
| Direct render inspection | Printed all 8 frames of a full cycle at each width, confirmed the sweep is continuous (`[●·····]` -> `[•●····]` -> ... -> `[······]` -> wraps to `[●·····]`) with no blank gaps and no double-bright cells |
| Real terminal | **Not yet seen by the user.** Same as every other TUI change this session. |

## Next

Ask the user to confirm the scan bar reads clearly as "actively scanning,
sweeping" rather than a decorative flicker, at its current width and
speed (0.1s per frame, ~0.8s per full sweep at width 6).

**The large pending Library screen redesign is still not started** -- see
[`docs/HANDOFF.md`](../HANDOFF.md)'s "Pending: Library screen redesign"
section for the full spec and the open question about settings
persistence. Also still outstanding: real-hardware re-confirmation of
TASK-210/211/212, the TASK-213/214 banner/colours, and the TASK-216/217
mount-detection changes on real macOS/Windows/Linux-desktop hardware.
