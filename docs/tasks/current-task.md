# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-214` |
| Objective | User reported the TUI "turned black" -- turn off Textual's built-in dark theme and use the terminal's own native colours everywhere, per the explicit ask that started TASK-213 |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/app.py`:
  - `UsbversalApp.__init__` now passes `ansi_color=True` to `App.__init__`.
    This flips on Textual's `:ansi` CSS mode app-wide: `App`/`Screen`'s
    `background`/`color` (which normally resolve to fixed hex values from
    Textual's default theme -- `#121212`, `#E0E0E0`, etc.) instead resolve
    to Rich's `ColorType.DEFAULT`, meaning "emit no colour code at all,
    let the terminal use whatever it's already set to."
  - New `CSS` class variable neutralizes two stock widgets that still leak
    a fixed dark colour even with `ansi_color=True`: `Footer` (and its
    `FooterKey`/`.footer-key--key`/`.footer-key--description` children)
    has no `:ansi` rule of its own at all in Textual's source, and `Tree`'s
    own `:ansi` rule only covers its text/guides, not the widget's own
    `background: $surface`. Both forced to `background: transparent`
    (`color: ansi_default` for the Footer pieces, whose foreground was
    also hardcoded).

### Root cause

TASK-213 already committed to "no custom theme, native terminal colours"
as a design principle, but never actually verified that Textual's
*default* theme was off -- it wasn't. Every Textual `App` ships with a
dark theme active by default (fixed hex `$background`/`$foreground`/etc.),
regardless of anything an app's own screens do; TASK-213's work was all at
the screen-content level (no colours set on the banner/spinner) and never
touched the App/Screen background those widgets sit on top of, which is
what was actually painting solid dark-grey/near-black across the whole
terminal.

### Design decisions

- **`ansi_color=True`, not a custom CSS override of `$background`.**
  Textual ships this exact mechanism for "use the terminal's own palette
  instead of a fixed theme" -- reaching for it instead of hand-rolling
  `background: transparent` on `App`/`Screen` ourselves means every other
  built-in widget's own `:ansi` rules (already written by Textual, e.g.
  `LoadingIndicator`'s, `Tree`'s partial one) kick in for free too, rather
  than needing to override each one by hand.
- **Functional highlight colours left alone.** The tree's selection
  cursor (`.tree--cursor`, a blue highlight bar) and the progress bar's
  fill colour were not touched -- they convey real state (what's selected,
  how far along a sync is), which is a different thing from a background
  theme painted under content that has no informational reason to be any
  particular colour. The user's complaint was specifically about the
  screen looking solid black, not about there being any colour at all.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 249 passed, 4 skipped |
| Direct Rich `Style` inspection | Rendered a segment from the Home screen's banner and confirmed its style is `default on default` (was previously resolving to a fixed near-black `Color(18, 18, 18)` background); did the same for a bare `Footer` and `Tree` harness and confirmed both now resolve to `on default` as well, after the CSS override |
| Real terminal | **Not yet seen by the user.** This was diagnosed and fixed from the user's verbal report ("my tui turned black"), not a reproducible local crash -- there is no automated test asserting on rendered colour, since that's exactly the kind of thing this project's TUI suite can't currently exercise against a real terminal's actual palette. |

## Next

Ask the user to re-run the TUI and confirm the background now matches
their terminal's own colours (not a dark grey/black block) on both the
Home screen and the Library/Progress/Done screens. Also still outstanding:
real-hardware re-confirmation of TASK-210/211/212's fixes, and how the
TASK-213 banner/spinner actually render in their terminal.
