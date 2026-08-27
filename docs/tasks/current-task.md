# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-216` |
| Objective | Auto-detect a valid DJ USB under `/media/$USER/<device>` (real desktop Linux's udisks2/gvfs auto-mount location, as opposed to this project's own WSL dev environment's `/mnt/usb`), and show the mount that got opened on the Library screen |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/storage/mounts.py`:
  - `LinuxMediaScanner` (new) -- lists `/media/$USER/*` the same way
    `LinuxMntScanner` lists `/mnt/*`: one `MountPoint` per immediate child
    directory, skipping dotfiles, tagged `source="linux_media"`. `$USER`
    comes from `getpass.getuser()`, not a raw `os.environ["USER"]` read --
    it falls back to other means of finding the username on systems where
    that variable isn't set. An absent `/media/$USER` (no desktop
    auto-mounter running, e.g. this project's own WSL environment) is not
    an error -- just an empty list, same as `LinuxMntScanner` handles a
    missing `/mnt`.
  - `_CompositeScanner` (new) -- merges the mount lists from several
    scanners into one. `get_mount_scanner()` now returns
    `_CompositeScanner([LinuxMntScanner(), LinuxMediaScanner()])` on
    Linux instead of picking exactly one -- a real box could plausibly
    have mounts show up under either root, and `MountWatcher.poll()`
    already de-duplicates by path via a `set` diff, so merging is safe
    even if something briefly appeared in both.
- `app/tui/screens/library.py` -- `compose()` now yields
  `Static(f"Mounted: {self._library.mount}", id="mount-info")` above the
  tree (`text-style: dim`, no colour -- consistent with TASK-213/214's "no
  theme" stance). Shows whichever path actually got opened, regardless of
  whether it came from either scanner or was typed manually through
  TASK-215's path input.
- `tests/test_mounts.py` -- `LinuxMediaScanner` listing + empty-root
  cases, `_CompositeScanner`'s merge, and `get_mount_scanner` now
  asserting a composite of both scanner types on Linux (previously
  asserted `LinuxMntScanner` alone).

### Design decisions

- **A composite scanner, not a single scanner checking two roots.**
  Keeping `LinuxMntScanner`/`LinuxMediaScanner` as separate single-root
  scanners (each already had tests written against its own specific root)
  and merging them at `get_mount_scanner()` meant no existing behavior or
  test for `/mnt` scanning needed to change at all -- only the composition
  point did.
- **`getpass.getuser()`, not `os.environ["USER"]` directly.** More
  portable across however the user's environment ended up configured;
  matches "assuming `$USER`" in intent without depending on that exact
  variable being set.
- **The mount line reads `library.mount`, not a separately threaded-through
  "how it was found" flag.** `UsbLibrary.mount` is already the resolved
  path that got opened, however it got there (auto-detected via either
  scanner, or typed manually) -- showing that instead of re-deriving or
  passing through provenance was the simpler, always-correct choice.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 259 passed, 4 skipped (5 new) |
| Direct `.region`/`render_line()` inspection | Built a real `UsbLibrary` against a synthetic stick and confirmed the `Mounted: <path>` line renders at the top of the Library screen, above the tree, with the tree's own region correctly starting one row lower |
| Real hardware | **Not yet confirmed.** This environment has no `/media/$USER` at all (it's WSL, using the pre-existing `/mnt/usb` bind-mount path) -- `LinuxMediaScanner` was verified only against a synthetic monkeypatched directory tree, never a real udisks2/gvfs auto-mount. |

## Next

Ask the user to confirm on a real desktop Linux machine: plug in a USB
stick, let it auto-mount under `/media/$USER/...`, and check that
`usbversal` finds it without needing the manual path entry, and that the
Library screen's "Mounted: ..." line shows the right path. Also still
outstanding from earlier tasks: real-hardware re-confirmation of
TASK-210/211/212, and how TASK-213/214/215's banner/spinner/colours/input
actually look and behave in a real terminal.
