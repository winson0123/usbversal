# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-218` |
| Objective | User: the manual-path/retry input should only appear once auto-scanning has actually failed, not by default -- the default should just be the spinner, quietly scanning, until it fails |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/screens/home.py`:
  - `_hide_input()` / `_reveal_input()` (new) -- the single place the path
    input's visibility is decided, called from `on_mount` (starts hidden),
    `_show_spinner()` (hides it), and `_show_error()` (reveals it).
    Hidden means both `display = False` **and** `disabled = True`:
    Textual still auto-focuses a hidden-but-enabled widget when it's the
    only focusable one on the screen (confirmed empirically -- without
    `disabled`, a user could type into an invisible field and it would
    silently work).
  - `_reveal_input()` only acts on the actual hidden -> visible
    transition (`if path_input.display: return`), not on every later
    `poll_mounts()` tick that re-confirms the same ongoing failure --
    otherwise it would steal focus back from wherever the user clicked
    once a second.
  - Placeholder text changed to "Press enter to retry auto-scan, or enter
    an absolute path" (from "insert a USB and press enter to retry, or
    type a path"), per the user's suggested wording.
  - `_open()` no longer separately manages the input's `disabled`/`focus`
    state on failure -- `_show_error()` (via `_reveal_input()`) is now the
    only place that happens, since it already needs to run there anyway.
- `tests/test_tui_home.py` -- new
  `test_input_is_hidden_and_unfocused_while_still_searching` (asserts
  `display`, `disabled`, and focus all say "not interactive" during
  ordinary searching); the four existing Tab/Enter/manual-path tests now
  call a `_force_error_state()` helper (`home._show_error(...)`) before
  interacting with the input, since revealing it is no longer automatic.

### Design decisions

- **Tied to the existing spinner/error toggle, not a third independent
  state flag.** `_show_spinner()`/`_show_error()` were already the two
  places that decided what the "second slot" under the banner shows;
  making the input's visibility follow the same two calls kept this a
  small, local change instead of introducing a parallel state machine
  that could drift out of sync with the existing one.
- **Disabled, not just hidden.** Caught by testing, not by reasoning
  about it first: Textual auto-focuses the sole focusable widget on a
  screen regardless of its `display` value. `display: none` alone left
  the hidden input focused and able to accept keystrokes -- invisible,
  but not actually inert.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 267 passed, 4 skipped (1 new) |
| Direct `.display`/`.disabled`/`app.focused` inspection | Confirmed via a throwaway script: on mount, `display=False`, `disabled=True`, `app.focused is None`; after `_show_error(...)`, `display=True`, `disabled=False`, input focused; the placeholder text reads correctly in the error state |
| Real terminal | **Not yet seen by the user.** Same as every other TUI change this session -- verified only via `Pilot`/direct widget inspection in this environment. |

## Next

Ask the user to confirm the new sequencing feels right in a real terminal:
plain spinner while it's still searching, no input in view at all, and the
input only appearing (focused, ready to type) once a scan attempt actually
fails. Also still outstanding from earlier tasks: real-hardware
re-confirmation of TASK-210/211/212, the TASK-213/214 banner/spinner/
colours, and the TASK-216/217 mount-detection changes on real macOS/Windows/
Linux-desktop hardware.
