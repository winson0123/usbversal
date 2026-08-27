# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-224` |
| Objective | User: "pressing enter doesnt restart auto scanning" -- found immediately after TASK-223 (below) shortened the scan timeout enough to actually try retrying by hand |
| Completed | 2026-08-27 |

### Scope (this pair of small, sequential fixes)

**TASK-223** — `app/tui/screens/home.py`: `HomeScreen.SCAN_TIMEOUT_S`
`15.0` -> `3.0`, per "can you change to 3 seconds? don't need that long."
No test changes needed -- both timeout tests already read
`home.SCAN_TIMEOUT_S` off the instance.

**TASK-224** — `on_input_submitted`'s empty-input branch now resets
`self._seen_invalid = False` and `self._searching_since =
time.monotonic()` before calling `poll_mounts()`. Root cause: once
`_seen_invalid` is set it never resets anywhere else (that's what stops
hopeful auto-checking after a real rejection) -- so a retry with nothing
new to find fell straight back into `_show_error(_NONE_FOUND)`,
re-printing the identical message with no visible change on screen.
That's indistinguishable from Enter having done nothing at all, which is
exactly what the user reported. `tests/test_tui_home.py` gained
`test_enter_on_empty_input_visibly_resumes_scanning`, asserting the
spinner reappears and `_seen_invalid` is actually `False` right after a
retry.

### Design decisions

- **Reset happens only on the explicit user retry, not on the recurring
  1s poll timer.** The timer must keep *confirming* the same failed
  state without flickering the spinner back on every tick once genuinely
  given up -- only a deliberate action (pressing Enter on an empty input)
  should visibly restart the search.
- **Committed together.** TASK-224 is a bug the shorter TASK-223 timeout
  made practical to notice and fix in the same sitting; both are tiny,
  sequential, and about the same retry flow, so splitting them into two
  commits would have added ceremony without adding clarity.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 276 passed, 4 skipped (1 new) |
| Direct state inspection | Confirmed: after the timeout fires (spinner hidden, input shown), pressing Enter flips it back (spinner shown, input hidden, `_seen_invalid` false) instead of leaving the red message and input untouched |
| Real terminal | **Not yet seen by the user.** Same as every other TUI change this session. |

## Next

Ask the user to confirm retry now visibly restarts scanning (spinner
resumes) rather than silently re-showing the same message.

**The large pending Library screen redesign is still not started** -- see
[`docs/HANDOFF.md`](../HANDOFF.md)'s "Pending: Library screen redesign"
section for the full spec and the open question about settings
persistence. Also still outstanding: real-hardware re-confirmation of
TASK-210/211/212, the TASK-213/214 banner/colours, and the TASK-216/217
mount-detection changes on real macOS/Windows/Linux-desktop hardware.
