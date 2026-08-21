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

## Gaps this TUI needs — none of these exist yet

1. **Per-playlist sync state (red / yellow / green).** Nothing computes it.
   Requires diffing each Rekordbox playlist's track set against the
   corresponding Serato crate: none present → red, some → yellow, all → green.
   This is the single largest missing piece and it gates screen 3.
   → **TASK-110**

2. **A playlist *tree*.** `Playlist` carries `parent_id`, but every consumer
   flattens it. The TUI needs real parent/child nesting with per-node
   aggregate sync state. → **TASK-111**

3. **"Is this a valid DJ USB?" as one call.** Screens 1–2 need a single
   readiness verdict, not a library list to interpret. Note that an
   **unmounted mount point still passes `resolve_mount_path`** — `/mnt/usb`
   persists as an empty directory when the stick is pulled, so emptiness must
   read as *no USB*, not as a valid path. → **TASK-112**

4. **Removable-media polling.** Detection today is a one-shot scan. Screen 2
   needs to observe mounts appearing and disappearing over time, cheaply
   enough to run in a UI loop. `LibraryDiscovery` walks up to 25,000 nodes,
   which is far too heavy to poll. → **TASK-113**

5. **ETA on progress.** `JobProgress` carries `current`/`total` but no rate or
   time estimate, and `CliProgressRenderer` throttles to 10/s and prints
   lines. A TUI needs rate tracking to render a bar with a completion
   estimate. → **TASK-114**

6. **Batch sync over selected playlists.** `apply` runs a plan file and takes
   **one backup per operation**. Selecting 40 playlists must take a single
   backup up front and report per-playlist outcomes — the collect-and-report
   shape added in TASK-102 is the right base, but backup handling needs to
   hoist out of the per-operation loop. → **TASK-115**

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
