# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-225` |
| Objective | User: the placeholder text was truncated ("... or enter (absolute path)."), and Tab only completed to a common prefix rather than letting them step through the available directories |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/tui/screens/home.py`:
  - **Truncation fix.** New `_RETRY_HINT = "Press enter to retry
    auto-scan."` constant. `_show_error(message)` now renders
    `f"{message} {_RETRY_HINT}"` -- the retry hint moved out of the
    input's placeholder (which had a fixed `width: 46` and was
    truncating it) and into the status line, which spans the whole
    screen width. The placeholder shrank to just "or enter an absolute
    path…".
  - **Tab-cycling.** `_complete_path()` (common-prefix completion)
    replaced by `_match_candidates(partial) -> list[str]`, which lists
    every matching *directory* (not files -- a file can never be a
    mount root, so they're excluded now rather than only incidentally
    handled by the old trailing-slash check). `_PathInput` gained
    `self._cycle: tuple[list[str], int] | None`: each Tab press advances
    to the next candidate, wrapping back to the first after the last.
    Typing something that doesn't match wherever the cycle last left
    the value starts a fresh cycle from the new text -- detected simply
    by comparing `self.value` against the candidate the previous Tab
    press set (`if self.value == matches[index]`), no separate
    "did the user type since" tracking needed.
- `tests/test_tui_home.py`:
  - `_complete_path`'s three unit tests replaced with three for
    `_match_candidates` (lists all matches, excludes files, empty on no
    match/bad parent).
  - The Tab pilot test replaced with `test_tab_cycles_through_matching_directories`
    (steps through two candidates and confirms the wrap), plus a new
    `test_typing_after_a_tab_cycle_starts_a_fresh_one`.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 277 passed, 4 skipped |
| Direct render inspection | Confirmed the status line now reads `"Did not detect a valid DJ USB Press enter to retry auto-scan."` and the placeholder reads `"or enter an absolute path…"` |
| Real terminal | **Not yet seen by the user.** Same as every other TUI change this session. |

## Next

Ask the user to confirm: the placeholder/error text no longer looks cut
off, and pressing Tab repeatedly now visibly steps through each matching
directory one at a time rather than only filling a partial common prefix.

**The large pending Library screen redesign is still not started** -- see
[`docs/HANDOFF.md`](../HANDOFF.md)'s "Pending: Library screen redesign"
section for the full spec and the open question about settings
persistence. Also still outstanding: real-hardware re-confirmation of
TASK-210/211/212, the TASK-213/214 banner/colours, and the TASK-216/217
mount-detection changes on real macOS/Windows/Linux-desktop hardware.
