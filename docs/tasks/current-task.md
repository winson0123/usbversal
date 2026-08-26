# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-26

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-203` |
| Objective | A cheap mount-appeared/disappeared watch, so the TUI's "Detect" screen can observe a stick being plugged in without repeating `LibraryDiscovery`'s ~25,000-node walk every tick |
| Completed | 2026-08-26 |

### Scope

Files touched:

- `app/storage/mount_watch.py` (new) — `MountChangeKind`, `MountChange`,
  `MountWatcher`: `poll()` diffs `MountScanner.list_mounts()` against the
  previous poll's set of paths and reports what appeared or disappeared
- `tests/test_mount_watch.py` (new) — first poll reports existing mounts as
  appeared, an unplugged stick reports as disappeared, no change produces no
  events, a swap in one poll reports both an appearance and a disappearance,
  changes come back sorted, and two watchers don't share state
- `docs/planning/interactive-tui.md`, `docs/tasks/backlog.md`, `docs/state/*.json`

### Design decisions

- **Only tracks mount *presence*, not DJ USB validity.** `MountScanner.list_mounts()`
  is a directory listing; deciding whether a newly appeared mount is a valid
  Rekordbox/Serato stick is `services.library.probe_mount`'s job (also
  stat-only, so still cheap per appearance, but a separate concern the
  watcher doesn't need to know about).
- **Stateful by design, one `MountWatcher` per poll loop.** It holds the
  previous poll's mount set as instance state; a fresh instance has no memory
  of a previous one, which is intentional (each caller owns its own watch)
  and has a test.
- **First poll reports everything present as appeared.** There's no prior
  state to diff against, so this is the only sensible behaviour, and it's the
  one the TUI flow wants anyway: on startup, whatever a first poll finds is
  exactly what needs a validity check.
- **No new dependency and no threading/async.** `poll()` is a synchronous,
  single-call diff; whatever drives the UI loop (a timer, `JobRunner`, plain
  `while`) decides the cadence. That decision belongs with TASK-206 (TUI
  framework choice), not this task.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 189 passed, 3 skipped (no stick mounted; skips are the two `/mnt/usb` integration tests and the PyInstaller build) |
| `.venv/bin/python -m app.cli --help` | all commands listed (unchanged) |

## Next

`TASK-204` (progress rate + ETA) is the last self-contained M11 groundwork
item. After that, the only M11 item left is `TASK-206` (TUI framework ADR +
shell) — a `textual`/`prompt_toolkit`/`rich`/`curses` choice that's a decision
point, not something to pick unilaterally.
