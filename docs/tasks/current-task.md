# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-213` |
| Objective | Home screen redesign: centered ASCII banner, a spinning glyph while detecting, an error message that replaces the spinner (not the banner) on scan failure -- no custom theme colours, just the terminal's own foreground plus Rich markup where it adds information |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/screens/home.py`:
  - `_BANNER` -- a fixed "usbversal" wordmark (shade/block-drawing
    characters, user-supplied), always visible.
  - `_Spinner` (new `Static` subclass) -- ticks through four quarter-circle
    frames (`◐◓◑◒`) on a 0.1s interval; no colour set on it, so it renders
    in whatever the terminal's default foreground is.
  - `compose()` nests banner/spinner/status each in their own `Center`
    (full-width, centers its one child) inside an outer `CenterMiddle`
    (centers that whole group vertically in the screen). Each item needed
    its own `Center` wrapper, not just `width: auto` under the shared
    `CenterMiddle` -- Textual's `align: center middle` centers the *group's
    bounding box* (sized to the widest child) as one block, left-anchoring
    narrower children inside it, not each child independently. Confirmed
    empirically by reading each widget's `.region` before and after adding
    the wrappers.
  - `_show_spinner()` / `_show_error()` replace the old free-text `_show()`:
    the spinner and the status `Static` occupy the same slot under the
    banner and are mutually exclusive (`display` toggled), matching the
    request that the error message *replace* the spinner rather than sit
    alongside it. The error text is wrapped in `[red]...[/red]` -- the one
    place colour is used at all, and it degrades to a colourless terminal
    automatically since it's Rich markup, not a hardcoded ANSI code.
  - Dropped the old "Ready: mount -- N playlists" flash message; the
    screen is replaced by `LibraryScreen` immediately on success, so there
    was nothing for a viewer to actually read there.
- `tests/test_tui_home.py` -- the "searching" test now asserts the spinner
  is visible and `#status` is hidden (previously asserted status text);
  the "none found" test additionally asserts the reverse. Behavioural
  assertions (which library gets opened, that Serato gets bootstrapped,
  that polling stops once a library is open) are unchanged.

### Design decisions

- **No custom Textual theme.** Per the user's explicit ask ("i dont need
  the features of themes, just take the native terminal colours, and
  support the rich text colours if terminal does") -- nothing here sets
  `color:`/`background:` via Textual's `$primary`/`$boost` theme variables
  (which `LoadingIndicator`, Textual's built-in spinner widget, does use --
  that's why this task hand-rolled `_Spinner` instead of reaching for the
  stock widget). The only colour anywhere is the `[red]` Rich markup on
  the error text, which is exactly "rich text colour, degrades on a
  terminal that doesn't support it" rather than a theme.
- **Banner art taken verbatim from the user**, not generated. They were
  shown four candidates (a hand-made block font, and figlet's `standard`/
  `slant`/`small_slant` outputs, confirmed via a scratch `pyfiglet`
  install) and picked their own alternative instead -- used as given.
- **Spinner and error message share one slot, not two independent ones.**
  The user's phrasing ("error message on scan failed, replacing circle
  spinning") describes one region that changes mode, not a spinner that
  keeps spinning next to a growing status line -- implemented as two
  widgets in the same position with `display` toggled between them.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 249 passed, 4 skipped |
| Direct `widget.render_line()`/`.region` inspection | Confirmed banner (36 wide), spinner (1 wide), and the error text (29 wide) each land independently centered in an 80-column screen (x=22, x=39, x=25 respectively -- each `(80-width)//2`), and that the spinner is hidden exactly when the error text is shown and vice versa |
| Real terminal | **Not yet seen by the user.** Verified only via headless `Pilot`/render-line inspection in this environment. |

## Next

Ask the user to run `python -m app.tui` (or the packaged binary) and confirm
the banner/spinner/error layout looks right in their actual terminal --
centering, glyph rendering (the block-drawing banner and the spinner both
depend on the terminal's font support), and that red actually renders as
red where their terminal has colour. Also still outstanding from
TASK-210/211/212: re-confirmation that the Library screen's columns line
up, "All playlists" collapses, and the app exits cleanly without the
drop-on-wrong-thread crash.
