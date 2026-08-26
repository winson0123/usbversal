# Interactive TUI (Planning)

**Status:** planned — M11, not started
**Related:** [serato-index-bootstrap.md](serato-index-bootstrap.md),
[ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md)

The argparse CLI in `app/cli/` is a **test harness for the service layer**, not
the shipped product. The distributed binary is an interactive terminal UI.
This document records the target so service-layer work can be shaped to feed it
rather than retrofitted later.

## Target flow

| # | Screen | Behaviour |
|---|--------|-----------|
| 1 | Waiting | `Searching for valid DJ USBs…` / `Did not detect a valid DJ USB` / `Searching for rekordbox exported USBs…` |
| 2 | Detect | A USB plugged in **while the screen is open** is picked up automatically and checked for rekordbox→Serato sync validity |
| 3 | Library | Playlist tree. Select all at top level or descend per playlist. Arrow keys move, space toggles, enter confirms. Traffic-light text: **red** not synced, **yellow** partially synced, **green** fully synced |
| 4 | Progress | Progress bar with estimated time to completion |
| 5 | Done | Completion summary. Enter returns to the library view, Esc exits |

## What the service layer already provides

| Need | Status |
|------|--------|
| Enumerate mounts | `storage.mounts.get_mount_scanner().list_mounts()` |
| Validate a mount path | `storage.mounts.resolve_mount_path()` |
| Detect libraries on a mount | `storage.discovery.LibraryDiscovery.detect_on_mount()` |
| Read playlists (with `parent_id`) | `services.playlist_service.list_rekordbox_playlists()` |
| Read crates | `services.crate_service.list_serato_crates()` |
| Async work + cooperative cancel | `jobs.runner.JobRunner` |
| Progress events with `current`/`total` | `core.events.JobProgress` |
| Error taxonomy for rendering | `services.errors` |

## Gaps this TUI needs

> Task IDs below are as originally planned (110–115) and are stale — see the
> note at the top of `docs/tasks/backlog.md` M11. Current IDs and status:

1. ~~**Per-playlist sync state (red / yellow / green).**~~ Done — TASK-111
   (`playlist_sync_states`), tracked as TASK-200 in the current backlog.

2. ~~**A playlist *tree*.**~~ Done — TASK-201, `core.playlist_tree.build_playlist_tree`
   nests the flat `parent_id`-linked list, and `services.sync_service.playlist_tree_sync_states`
   adds the per-node aggregate state a folder needs (green only if every
   descendant is synced, red only if none are, yellow otherwise — including an
   empty folder, which reads as red rather than vacuously green).

3. **"Is this a valid DJ USB?" as one call.** Screens 1–2 need a single
   readiness verdict, not a library list to interpret. Note that an
   **unmounted mount point still passes `resolve_mount_path`** — `/mnt/usb`
   persists as an empty directory when the stick is pulled, so emptiness must
   read as *no USB*, not as a valid path. → Done, TASK-110 (`probe_mount`),
   tracked as TASK-202.

4. ~~**Removable-media polling.**~~ Done — TASK-203, `storage.mount_watch.MountWatcher`.
   Each `poll()` costs one `MountScanner.list_mounts()` call, diffed against
   the previous poll; no `LibraryDiscovery` walk. It only reports mount
   presence, not DJ USB validity — the caller runs `probe_mount` (also
   stat-only) on whatever appears.

5. **ETA on progress.** `JobProgress` carries `current`/`total` but no rate or
   time estimate, and `CliProgressRenderer` throttles to 10/s and prints
   lines. A TUI needs rate tracking to render a bar with a completion
   estimate. → **TASK-204**, still open.

6. ~~**Batch sync over selected playlists.**~~ Done — TASK-114/TASK-205,
   `sync_playlists()` takes one backup for the whole run and reports
   per-playlist outcomes.

## Constraints carried over

- Writes stay backup-gated: a `WriteContext` cannot be built without a verified
  manifest, and the TUI must surface a failed gate rather than proceed.
- Stage 2 (cues/beatgrids) mutates audio files and must stay behind an explicit
  opt-in in the UI, never bundled into a default "sync".
- Nothing under `PIONEER/` or `Contents/` is written during playlist sync.

## Library choice

Not decided. Requirements: arrow/space/enter/esc key handling, coloured text,
a progress bar, and no dependency that breaks PyInstaller one-file packaging
(see [ADR 0003](../decisions/0003-use-pyinstaller.md)). Candidates worth an ADR:
`textual`, `prompt_toolkit`, `rich` + manual key handling, or plain `curses`.
