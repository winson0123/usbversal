# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-217` |
| Objective | User: remove WSL artifacts, since real deployment is Windows/Linux/macOS (not WSL); also add an environment-variable override for a setup none of the automatic scanners cover |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/storage/mounts.py`:
  - **Removed `LinuxMntScanner`** and its `_DEFAULT_EXCLUDED_MNT_NAMES`
    (`{"wsl", "wslg", "c"}`) entirely. That exclusion list only made sense
    against this project's own WSL dev sandbox's `/mnt` layout -- a real
    native Linux desktop doesn't put anything meaningful under `/mnt` by
    default (auto-mounted removable media goes to `/media/$USER`, already
    covered by `LinuxMediaScanner` from TASK-216), so this was purely a
    dev-environment artifact, not something real deployment needs.
  - **New `MacVolumesScanner`** -- scans `/Volumes/*` (excluding the
    `Macintosh HD` boot volume), the real macOS equivalent of
    `LinuxMediaScanner`. macOS was previously only a `_stub` flag in
    `repository-state.json` with no actual scanning logic behind it at
    all on the non-Windows branch of `get_mount_scanner()` -- it would
    have incorrectly tried `/mnt`/`/media/$USER` on a real Mac.
  - **New `EnvMountScanner`** -- reads a `USBVERSAL_MOUNT` environment
    variable as a single mount candidate, for a setup none of the
    automatic scanners cover (unusual auto-mount daemon, container, or
    just a path the user prefers). It's an ordinary `MountScanner`, not
    special-cased anywhere else, so it goes through the exact same
    discover -> probe -> open path as anything the platform scanners
    find.
  - `get_mount_scanner()` now branches three ways on `platform.system()`
    (`Windows` / `Darwin` / else -> Linux) instead of two, and always
    composes the platform scanner with `EnvMountScanner()`.
- Doc/CLI-help examples that said "e.g. /mnt/usb" throughout the app
  (`cli/main.py`, `services/backup_service.py`, `services/migration_service.py`,
  `services/crate_service.py`, `services/rollback_service.py`,
  `adapters/rekordbox/paths.py`, `adapters/serato/paths.py`,
  `storage/mounts.py`) were updated to "e.g. /media/$USER/MY_USB" -- the
  old example was really this dev sandbox's own bind-mount path, not a
  representative one for a real user on any of the three real deployment
  platforms.
- `tests/test_mounts.py` -- `LinuxMntScanner`'s test removed along with
  the class; new tests for `MacVolumesScanner` (lists volumes, excludes
  the boot volume, handles a missing `/Volumes` root) and `EnvMountScanner`
  (reads the variable, empty when unset, ignores a nonexistent path,
  configurable variable name); `get_mount_scanner` now has one test per
  platform confirming the right two-scanner composite.
- `docs/state/repository-state.json` -- `mount_scanner_macos_stub` ->
  `mount_scanner_macos: true` (genuinely implemented now, though still
  unverified on real hardware -- see `known_gaps`); noted that
  `primary_test_usb.linux_wsl`'s `/mnt/usb` is this dev sandbox's own test
  rig, not a deployment target, and that this session now reaches it via
  `USBVERSAL_MOUNT=/mnt/usb` instead of the removed automatic `/mnt` scan.

### Design decisions

- **Removed `LinuxMntScanner` outright rather than keeping it as an
  opt-in extra.** Once `EnvMountScanner` exists, anyone who genuinely
  needs `/mnt`-style detection (this project's own WSL dev/test sandbox
  included) has a strictly more precise tool for it -- point
  `USBVERSAL_MOUNT` at the exact path -- rather than a scanner that walks
  an entire directory guessing which entries aren't "system binds."
- **`EnvMountScanner` composed on every platform, not just as a Linux
  fallback.** The problem it solves (a setup the automatic scanner can't
  find) isn't Linux-specific, and composing it uniformly kept
  `get_mount_scanner()`'s three-way branch simple -- one platform
  scanner, plus this, always.
- **macOS excludes the boot volume by name (`"Macintosh HD"`), not by any
  more general heuristic.** That's the actual, standard default name
  `/Volumes` always contains for the startup disk; a more general "skip
  the root filesystem's own volume" check would need machinery (comparing
  device IDs, or shelling out to `diskutil`) that isn't needed for
  something this project can name directly, and is easy to verify or
  adjust later against a real Mac.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 266 passed, 4 skipped (7 new, 1 removed) |
| Real hardware | **Not confirmed.** `MacVolumesScanner` and `WindowsMountScanner` are both verified only against monkeypatched directory trees in this environment -- neither has ever run against real macOS or Windows hardware. This environment's own dev/test USB stick (`/mnt/usb`) was re-verified reachable via `USBVERSAL_MOUNT=/mnt/usb` logically (same `EnvMountScanner` test coverage as any other path), but not re-run through the full TUI end to end after this change. |

## Next

Ask the user to confirm on real macOS and Windows hardware (or at least a
real desktop Linux session for `/media/$USER`) that auto-detection still
works, and that `USBVERSAL_MOUNT` picks up a path none of the automatic
scanners find. If this agent needs to keep testing against this
environment's own stick, use `USBVERSAL_MOUNT=/mnt/usb python -m app.tui`
now that the automatic `/mnt` scan is gone. Also still outstanding from
earlier tasks: real-hardware re-confirmation of TASK-210/211/212, and how
TASK-213/214/215's banner/spinner/colours/input actually look and behave
in a real terminal.
