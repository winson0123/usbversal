# Completed Tasks

Historical record. Mirror of `docs/state/task-state.json` history.

---

## TASK-INIT-001 — Initialize repository harness + documentation scaffolding

| Field | Value |
|-------|-------|
| Completed | 2026-05-22 |
| Objective | Agent operating system, docs structure, JSON state placeholders |
| Verification | File tree complete; no runtime logic |

**Deliverables:**

- `AGENT.md` — execution contract
- `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`
- `docs/architecture/`, `docs/adapters/`, `docs/jobs/`, `docs/storage/`
- `docs/decisions/` ADRs 0001–0003
- `docs/tasks/`, `docs/state/`, `docs/workflows/`
- Valid JSON state files

---

## TASK-011 — Backup copy + manifest.json

| Field | Value |
|-------|-------|
| Completed | 2026-05-25 |
| Objective | Timestamped Rekordbox file backup with SHA-256 manifest |
| CLI | `python -m app.cli backup --mount /mnt/usb` |

---

## TASK-030 — Rekordbox read-only playlist listing

| Field | Value |
|-------|-------|
| Completed | 2026-05-25 |
| Objective | `list-playlists` using rbox on `exportLibrary.db` |
| Verification | pytest 20 passed; /mnt/usb returned 70 playlists |

**Notes:** Classic `export.pdb` (DeviceSQL) not supported; use One Library export or future adapter.

---

## TASK-050 — USB mount scanner and DJ library discovery

| Field | Value |
|-------|-------|
| Completed | 2026-05-25 |
| Objective | `python -m app.cli scan` with read-only Rekordbox/Serato detection |
| Verification | ruff pass, pytest 12 passed, /mnt/usb live scan |

**Deliverables:** `app/` package, `pyproject.toml`, mount scanner, `LibraryDiscovery`, events, thin CLI.

---

## TASK-061 — `/mnt/usb` integration validation

| Field | Value |
|-------|-------|
| Completed | 2026-06-05 |
| Objective | Validate migrate-playlist on real USB; document Serato Analyze Files workflow |
| Doc | `docs/workflows/usb-integration-validation.md` |

**Results:** Pocket playlist 80/80 path match; Serato Pocket crate 80 tracks; pytest 49 passed.

---

## TASK-053 — `apply` with JSON plan file

| Field | Value |
|-------|-------|
| Completed | 2026-06-05 |
| Objective | Batch operations via `apply --plan`; v1 supports `migrate_playlist` |
| Doc | `docs/planning/apply-plan-format.md` |

---

## TASK-060 — PyInstaller packaging

| Field | Value |
|-------|-------|
| Completed | 2026-06-06 |
| Objective | One-file Linux binary + smoke tests |
| Artifact | `dist/usbversal` (~16 MB) |

---

## TASK-126 — Correct the stale guidance and document location.sqlite

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | Fix the beatgrid-only-for-constant-tempo claim in `analysis-data-study.md` and document `location.sqlite` in the Serato schema notes |
| Verification | Documentation only |

**Note:** this record and the two below were backfilled into
`completed-tasks.md` at TASK-130; `docs/state/task-state.json` is the
authoritative history for everything between TASK-060 and TASK-126 that this
file never recorded — see `git log` for the actual sequence.

---

## TASK-127 — Cover the ANLZ reader with tests

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | `tests/test_anlz.py` — section walk, hot/memory cue distinction, slot conversion, RGB read, tempo scaling, malformed/missing-file handling |
| Verification | pytest: 8 new tests, all passing |

---

## TASK-130 — Wire grids, cues and the library index into `sync_playlists`

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | `sync_playlists` writes Rekordbox beatgrids/hot cues into audio tags and updates `location.sqlite`, not just crates and `database V2` |
| Verification | ruff ✓ ruff format ✓ pytest 157 passed / 3 skipped |

**Note:** exercised against synthetic fixtures only (a real WAV with real
Serato frames, hand-built ANLZ containers); not yet re-run against the test
stick. See `docs/tasks/current-task.md` and `docs/HANDOFF.md`.

---

## TASK-131 — Move write verification into `write_geob`

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | Size, audio-stream hash, and frame read-back checks run before any byte reaches disk; a failure raises `TagFormatError` and leaves the original file untouched |
| Verification | ruff ✓ ruff format ✓ pytest 164 passed / 3 skipped |

---

## TASK-132 — Codify the index BPM rules

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | `correct_index_bpm()` — library-wide `location.sqlite` correction to each track's first-beat tempo, independent of playlist membership |
| Verification | ruff ✓ ruff format ✓ pytest 169 passed / 3 skipped |

---

## TASK-133 — Never-clobber regression test

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | `tests/test_never_clobber.py` — proves `write_geob` never disturbs a Mixed In Key or other foreign vendor GEOB frame |
| Verification | ruff ✓ ruff format ✓ pytest 173 passed / 3 skipped |

---

## TASK-201 — Playlist tree model

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | `core/playlist_tree.py` nests the flat `parent_id`-linked list; `sync_service.playlist_tree_sync_states` adds the per-folder sync-state rollup the TUI's library screen needs |
| Verification | ruff ✓ ruff format ✓ pytest 183 passed / 3 skipped |

---

## TASK-203 — Removable-media polling

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | `storage/mount_watch.py`'s `MountWatcher.poll()` — cheap mount-appeared/disappeared diffing for a UI loop, without `LibraryDiscovery`'s heavy walk |
| Verification | ruff ✓ ruff format ✓ pytest 189 passed / 3 skipped |

---

## TASK-204 — Progress rate + ETA

| Field | Value |
|-------|-------|
| Completed | 2026-08-26 |
| Objective | `jobs/progress_rate.py`'s `ProgressRateTracker` — whole-run rate and ETA from `current`/`total` samples, wired into `CliProgressRenderer` |
| Verification | ruff ✓ ruff format ✓ pytest 200 passed / 3 skipped |

---

## TASK-206 — TUI framework ADR + shell

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | ADR 0009 picks `textual`; `app/tui/` scaffolded with `UsbversalApp` and the Home screen (steps 1-2, Waiting/Detect); verified with a real PyInstaller build |
| Verification | ruff ✓ ruff format ✓ pytest 204 passed / 4 skipped; real `pyinstaller` build's `tui` subcommand confirmed rendering headless |

---

## TASK-207 — TUI Library screen

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | `app/tui/screens/library.py` — the playlist folder tree with per-node red/yellow/green state and multi-select; `HomeScreen` now hands off to it |
| Verification | ruff ✓ ruff format ✓ pytest 209 passed / 4 skipped |

---

## TASK-208 — TUI Progress + Done screens

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | `app/tui/screens/progress.py` — runs `sync_playlists` via a worker, renders live progress and a completion summary; the first point `sync_playlists` is reachable from the TUI |
| Verification | ruff ✓ ruff format ✓ pytest 219 passed / 4 skipped; manual end-to-end smoke (Home → Library → Progress → Done → Library) with real screens chained together |

---

## TASK-075 — Nested playlist folders → `Parent%%Child.crate`

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | `crate_name_for()` encodes ancestor folders with `%%`, so same-named playlists in different folders stop colliding on one crate file |
| Verification | ruff ✓ ruff format ✓ pytest 226 passed / 4 skipped |

---

## TASK-076 — Bootstrap `_Serato_` on a rekordbox-only stick

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | `services/bootstrap_service.py`'s `bootstrap_serato_library()` creates an empty, valid Serato library when none exists; wired into the TUI's Home screen |
| Verification | ruff ✓ ruff format ✓ pytest 235 passed / 4 skipped |

---

## TASK-209 — Fix rbox thread-affinity crash on real hardware

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | `RekordboxThreadMixin` pins every `UsbLibrary.rekordbox` call to one dedicated thread, fixing a pyo3 process abort the TUI hit on its first real-hardware run |
| Verification | ruff ✓ ruff format ✓ pytest 239 passed / 4 skipped; **not yet re-confirmed against real hardware by this agent** — awaiting the user's re-run |

---

## TASK-210 — Library screen: refresh on resume, show synced/total counts

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Fix the Library screen showing stale sync state after a sync (needed an app restart to update), and add visible `x/x` synced/total counts per the user's request |
| Verification | ruff ✓ ruff format ✓ pytest 243 passed / 4 skipped; **not yet re-confirmed on real hardware** |

---

## TASK-211 — Library screen: true column alignment, "All playlists" node

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Fix genuinely jagged columns (Tree's guide/icon width varies per row; fixed-width padding alone can't compensate) and add a collapsible "All playlists" node that selects/collapses the whole library at once |
| Verification | ruff ✓ ruff format ✓ pytest 248 passed / 4 skipped; **not yet re-confirmed on real hardware** |

---

## TASK-212 — Fix rbox thread-affinity crash on TUI exit

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Fix a new user-reported crash on quit -- `PyOneLibrary is unsendable, but is being dropped on another thread` -- the same pyo3 thread-affinity rule TASK-209 fixed for *use*, but this time for *drop*: Textual tears the whole screen stack down from the main thread on quit, and whichever screen holds the last reference to the opened library triggers its Drop there |
| Verification | ruff ✓ ruff format ✓ pytest 249 passed / 4 skipped; **not yet re-confirmed on real hardware** -- this crash never reproduced in this environment at all, since the TUI test suite mocks the rekordbox adapter |

---

## TASK-213 — Home screen: centered ASCII banner, spinner, error state

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Redesign the Home (Waiting/Detect) screen per the user's request: a centered ASCII "usbversal" wordmark, a spinning glyph underneath while detecting, and an error message that replaces the spinner (not the banner) on scan failure -- native terminal colours only, no custom theme, Rich colour markup for the one place it's useful |
| Verification | ruff ✓ ruff format ✓ pytest 249 passed / 4 skipped; layout verified via direct `widget.render_line()`/`.region` inspection (each element independently centered); **not yet seen by the user in a real terminal** |

---

## TASK-214 — TUI: use native terminal colours instead of Textual's dark theme

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User reported the TUI "turned black" -- Textual's built-in theme paints `App`/`Screen` background as a fixed near-black hex (`#121212`) regardless of the user's own terminal colours, which is exactly the "theme" the user asked TASK-213 to avoid but hadn't actually been turned off yet |
| Verification | ruff ✓ ruff format ✓ pytest 249 passed / 4 skipped; confirmed via direct Rich `Style` inspection on rendered segments that App/Screen/Footer/Tree backgrounds now resolve to `default` (terminal-native) rather than a fixed hex; **not yet seen by the user in a real terminal** |

---

## TASK-215 — Home screen: retry-on-enter and manual path entry with Tab completion

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User asked: insert a valid USB and press enter to retry scanning, optionally type the path directly, with Tab completion |
| Verification | ruff ✓ ruff format ✓ pytest 256 passed / 4 skipped (7 new tests: path-completion unit tests plus Pilot-driven Tab/Enter/manual-path/failure-recovery tests) |

---

## TASK-216 — Detect USB sticks under /media/$USER, show the mount on the Library screen

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User asked to auto-detect a valid DJ USB under `/media/$USER/<device>` -- where udisks2/gvfs auto-mounts removable media on a real desktop Linux session, as opposed to this project's own WSL dev environment's `/mnt/usb` -- and show the mount that got opened somewhere on the Library screen |
| Verification | ruff ✓ ruff format ✓ pytest 259 passed / 4 skipped (5 new: `LinuxMediaScanner` listing + empty-root cases, `_CompositeScanner` merge, `get_mount_scanner` now returning a composite on Linux); confirmed via direct `.region`/`render_line()` inspection that the mount line renders as expected above the tree |

---

## Template (for future entries)

```markdown
## TASK-XXX — Title

| Field | Value |
|-------|-------|
| Completed | YYYY-MM-DD |
| Commit | `<hash>` |
| Verification | ruff ✓ pytest ✓ |
```
