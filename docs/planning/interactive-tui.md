# Interactive TUI (Planning)

**Status:** All 5 target-flow screens built and wired end to end (TASK-206
through TASK-208) -- Waiting → Detect → Library → Progress → Done, with
`sync_playlists()` actually reachable and running from the TUI. Not yet
validated against real hardware (`/mnt/usb`), only synthetic fixtures; not
yet the packaged binary's default action (still `usbversal tui`
/ `python -m app.tui`, alongside the CLI test harness).
**Related:** [serato-index-bootstrap.md](serato-index-bootstrap.md),
[ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md),
[ADR 0009](../decisions/0009-use-textual-for-the-tui.md)

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
| 5 | Done | Completion summary. Enter returns to the library view. Quit is ^Q. |

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

5. ~~**ETA on progress.**~~ Done — TASK-204, `jobs.progress_rate.ProgressRateTracker`.
   `CliProgressRenderer` now appends a rate and ETA to its lines once a job
   has two samples; a future TUI progress bar would use the same tracker
   rather than parsing the CLI's text output.

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

**Decided: `textual`.** See [ADR 0009](../decisions/0009-use-textual-for-the-tui.md)
for the full comparison against `prompt_toolkit`, `rich` + manual key
handling, and `curses`. `app/tui/` has the app shell and the Home screen
(steps 1-2); Library (step 3, TASK-207) and Progress/Done (steps 4-5,
TASK-208) are next.
