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

## TASK-217 — Remove WSL-only /mnt scanning, add a real macOS scanner and USBVERSAL_MOUNT override

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User: remove WSL artifacts, since real deployment is Windows/Linux/macOS (not WSL); also add an environment-variable override for a setup none of the automatic scanners cover |
| Verification | ruff ✓ ruff format ✓ pytest 266 passed / 4 skipped (7 new: `MacVolumesScanner` listing + empty-root cases, `EnvMountScanner` set/unset/missing-path/custom-var-name cases, `get_mount_scanner` composite checks for all three platforms; `LinuxMntScanner`'s own test removed along with the class) |

---

## TASK-218 — Home screen: only show manual path entry after auto-scan fails

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User: the "insert a USB and press enter to retry" input should only appear once auto-scanning has actually failed, not by default -- the default should just be the spinner, quietly scanning, until it fails |
| Verification | ruff ✓ ruff format ✓ pytest 267 passed / 4 skipped (1 new, 4 rewritten to force the error state first since that's now the only way the input becomes reachable) |

---

## TASK-219 — Progress screen: verbose per-track log, green/red colour instead of theme

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User: "need verbose, i dont know what is happening on progress bar. green verbose, red on error" -- the single overwriting status line didn't say which track was being processed or whether any had failed |
| Verification | ruff ✓ ruff format ✓ pytest 273 passed / 4 skipped (6 new: the failing-track case for `on_progress`'s new signature, two `RichLog` colour/content tests, three `DoneScreen` colour tests) |

---

## TASK-220 — Home screen: scanning caption + a more noticeable pulsing-dot spinner

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User: "well i dont see the verbose message of scanning usbs when the first screen shows. only the spinning circle" -- refined mid-implementation to a fixed caption ("Automatically detecting for a DJ USB…") and a bigger, pulsing-dot spinner ("its quite small") |
| Verification | ruff ✓ ruff format ✓ pytest 273 passed / 4 skipped |

---

## TASK-221 — Home screen: sweeping scan-bar spinner instead of a pulsing dot

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User asked to replace the single pulsing dot with a `[···••●]`-style bar where the bright point sweeps left to right, repeating; then asked for the bar's resting fill to be the smallest dot rather than blank space, and for the whole bar to be narrower |
| Verification | ruff ✓ ruff format ✓ pytest 273 passed / 4 skipped (no behavioural test changes needed -- `_Spinner`'s public shape, id, and CSS are unchanged, only its internal frame content) |

---

## TASK-222 — Home screen: scan timeout so nothing plugged in does not spin forever

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User: "now stuck on the screen? when usb not plugged in, should have retry/timeout" -- if nothing was ever plugged in at all (as opposed to something invalid being found), the screen would spin indefinitely with no way to reach the manual-path input |
| Verification | ruff ✓ ruff format ✓ pytest 275 passed / 4 skipped (2 new: still spinning well under the timeout, and the timeout firing reveals the same error/input state a rejection would) |

---

## TASK-223 — Home screen: shorten the scan timeout to 3 seconds

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User: "can you change to 3 seconds? don't need that long" |
| Verification | ruff ✓ ruff format ✓ pytest 275 passed / 4 skipped (no test changes needed -- both timeout tests already read `home.SCAN_TIMEOUT_S` off the instance) |

---

## TASK-224 — Home screen: retry actually resumes scanning instead of re-printing the same error

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User: "pressing enter doesnt restart auto scanning" -- found immediately after TASK-223 shortened the timeout enough to actually try retrying by hand |
| Verification | ruff ✓ ruff format ✓ pytest 276 passed / 4 skipped (1 new: retry visibly flips the screen back to the spinner state, not just re-showing the identical error) |

---

## TASK-225 — Home screen: fix truncated placeholder, real Tab-cycling through directories

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | User: the input's placeholder text was visibly truncated ("... or enter (absolute path)."), and Tab only ever completed to a common prefix rather than actually stepping through the available directories |
| Verification | ruff ✓ ruff format ✓ pytest 277 passed / 4 skipped (`_complete_path`'s 3 tests replaced with 3 for `_match_candidates`; the Tab pilot test replaced with a cycling one, plus a new one confirming a hand-edit mid-cycle starts fresh) |

---

## TASK-226 — Move TUI session-open into prepare_library

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Home no longer orchestrates bootstrap + open + a discarded list_playlists; `prepare_library` is the session-open path |
| Verification | ruff ✓ ruff format ✓ pytest 278 passed / 4 skipped |

---

## TASK-227 — Home screen: explicit HomePhase instead of _seen_invalid

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Replace the `_seen_invalid` flag pile with `HomePhase` |
| Verification | ruff ✓ ruff format ✓ pytest 278 passed / 4 skipped |

---

## TASK-228 — Extract PathInput widget from the Home screen

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Move PathInput + match_candidates to `app/tui/widgets/path_input.py` |
| Verification | ruff ✓ ruff format ✓ pytest 278 passed / 4 skipped |

---

## TASK-229 — Unify TUI screen library attribute name

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Home/Library/Progress all use `library`; quit clears that one name |
| Verification | ruff ✓ ruff format ✓ pytest 278 passed / 4 skipped |

---

## TASK-230 — Replace Linux/macOS mount scanner twins with ChildDirectoryScanner

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | One directory-listing scanner; Linux and macOS only differ by root and exclude |
| Verification | ruff ✓ ruff format ✓ pytest 277 passed / 4 skipped |

---

## TASK-231 — Library labels as Text; leaf_ids on PlaylistTreeSyncState

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Safer tree labels; playlist ids live with the sync tree |
| Verification | ruff ✓ ruff format ✓ pytest 277 passed / 4 skipped |

---

## TASK-232 — Quit feels instant: park library handles, Drop after the UI is gone

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Restore the terminal on `q`; drop PyOneLibrary on the rekordbox thread after unmount |
| Verification | ruff ✓ ruff format ✓ pytest 279 passed / 4 skipped |

---

## TASK-233 — Skip the alt screen on ConPTY so quit is not a 1s buffer swap

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Draw on the main buffer under WSL / Windows Terminal; keep the alt screen elsewhere |
| Verification | ruff ✓ ruff format ✓ pytest 284 passed / 4 skipped |

---

## TASK-234 — Split sync_playlists and the other CC>11 functions in sync_service

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Name each sync step; public signatures unchanged |
| Verification | ruff ✓ ruff format ✓ pytest 284 passed / 4 skipped |

---

## TASK-235 — Split write_geob, build_track_record, and _find_playlist

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Clear the last CC 11+ functions in app/ |
| Verification | ruff ✓ ruff format ✓ pytest 284 passed / 4 skipped |

---

## TASK-236 — Bring remaining app/ functions under CC 6

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Name the remaining CC 6–10 steps; no function in app/ left at 6+ |
| Verification | ruff ✓ ruff format ✓ pytest 284 passed / 4 skipped |

---

## TASK-237 — Flatten the TASK-236 helper explosion

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Inline one-off extracts; keep only splits that still earn their name |
| Verification | ruff ✓ ruff format ✓ pytest 284 passed / 4 skipped |

---

## TASK-238 — Fold sync_analysis.py back into sync_service.py

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Restore the TASK-235 module shape; keep CLI table and shared backup helpers |
| Verification | ruff ✓ ruff format ✓ pytest 284 passed / 4 skipped |

---

## TASK-239 — Commit the leftover test trim

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Keep consolidations that still cover the same behaviour; restore tests that still earn their keep |
| Verification | ruff ✓ ruff format ✓ pytest 281 passed / 4 skipped |

---

## TASK-240 — Remove the CLI

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Delete argparse harness; `usbversal` launches the TUI |
| Verification | ruff ✓ ruff format ✓ pytest 269 passed / 4 skipped |

---

## TASK-241 — Confirm ID3v2.3 and v2.4 MP3 GEOB writes

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Hand-built MP3 round-trips for both ID3 size encodings |
| Verification | ruff ✓ ruff format ✓ pytest 271 passed / 4 skipped |

---

## TASK-242 — FLAC Vorbis-comment Serato tags

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | Same BeatGrid / Markers2 payloads on FLAC; STREAMINFO and audio unchanged |
| Verification | ruff ✓ ruff format ✓ pytest 276 passed / 4 skipped |

---

## TASK-243 — Progress covers index and crate writes

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | `SyncProgress` phases for index, analysis, and crates |
| Verification | ruff ✓ ruff format ✓ pytest 276 passed / 4 skipped |

---

## TASK-244 — Drop TASK-090; `/mnt/usb` out of operator docs

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | DeviceSQL reader dropped; operators use auto-detect, not a hardcoded mount |
| Verification | ruff ✓ ruff format ✓ pytest 276 passed / 4 skipped |

---

## TASK-245 — Confirm `Parent%%Child` crate naming in Serato

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | `Gigs → Played → safety day` sync shows as a three-level crate; no empty parent files required |
| Verification | ruff ✓ ruff format ✓ pytest; user confirmation in Serato |

---

## TASK-246 — Record the three-level crate path

| Field | Value |
|-------|-------|
| Completed | 2026-08-27 |
| Objective | On-disk name is `Gigs%%Played%%safety day.crate` (Gigs → Played → safety day), not two levels |
| Verification | ruff ✓ ruff format ✓ pytest; crate file on the stick |

---

## TASK-247 — Host-side audio tag deltas

| Field | Value |
|-------|-------|
| Completed | 2026-08-28 |
| Objective | Backups on the host; audio stored as a tag-region delta, not a second copy of the song |
| Verification | ruff ✓ ruff format ✓ pytest 283 passed / 4 skipped |

---

## TASK-249 — Do not abort sync on leftover Markers2 base64

| Field | Value |
|-------|-------|
| Completed | 2026-08-28 |
| Objective | Drop one leftover `4n+1` Markers2 base64 character; one dirty tag must not abort the run |
| Verification | ruff ✓ ruff format ✓ pytest 285 passed / 4 skipped |

**Decision:** [ADR 0010](../decisions/0010-tolerate-leftover-markers2-base64.md) — the extra character is junk after a complete `COLOR`/`CUE`/`BPMLOCK`, already on the file's Serato GEOB. Drop one character (`69 → 68`), do not cut at 64.

---

## TASK-250 — Run `correct_index_bpm` on WONSIN

| Field | Value |
|-------|-------|
| Completed | 2026-08-28 |
| Objective | Write first-beat BPM into `location.sqlite` on the real stick |
| Verification | Dry-run 7/1286; live write 7 rows; backup `20260828T072224Z`; second dry-run 0; pytest 285 passed / 4 skipped |

**Findings:** [index-bpm-wonsin.md](../workflows/index-bpm-wonsin.md) — four half-tempo rows, three 0.01 float rows. Exact `!=` kept.

---

## TASK-253 — Read PCO2 cue colour from offset 28

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Stop writing black Serato cues; RGB is at PCP2 offset 28, not the last 3 bytes |
| Verification | ruff ✓ ruff format ✓ pytest 286 passed / 4 skipped |

**Findings:** [cue-colour-offset.md](../workflows/cue-colour-offset.md)

---

## TASK-254 — Keep `/` in crate names

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Rekordbox playlist names with `/` must not show as `_` in Serato |
| Verification | ruff ✓ ruff format ✓ pytest 287 passed / 4 skipped |

**Decision:** [crate-slash.md](../workflows/crate-slash.md) — fullwidth solidus, not `%%`.

---

## TASK-256 — Omit Rekordbox "CUE Analysis Playlist"

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Do not list or sync Rekordbox's regenerated analysis playlist |
| Verification | ruff ✓ ruff format ✓ pytest 289 passed / 4 skipped |

Rekordbox recreates `CUE Analysis Playlist` (also seen as `Cue Analysis Playlist`) on every export. Folders with that name are left alone.

---

## TASK-255 — Parent crate named after the volume

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | House every synced crate under a parent named after the thumbdrive |
| Verification | ruff ✓ ruff format ✓ pytest 292 passed / 4 skipped |

**Decision:** [volume-crate.md](../workflows/volume-crate.md) — `WONSIN%%Contents`, no empty parent file.

---

## TASK-251 — Confirm a variable-tempo grid in Serato

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Load Apt X Blue on a Serato deck and confirm the 4-marker ramp |
| Verification | User: grid follows; last marker 140.9 not 140 |

**Findings:** [apt-x-blue-grid.md](../workflows/apt-x-blue-grid.md). 2026-08-30 follow-up: six more encoder-matched tracks; outliers are Rekordbox.

---

## TASK-257 — Terminal beatgrid BPM is the settled last section

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Last marker BPM is the tempo that holds, not the first mid-ramp reading |
| Verification | ruff ✓ ruff format ✓ pytest 293 passed / 4 skipped |

**Findings:** [apt-x-blue-grid.md](../workflows/apt-x-blue-grid.md) — median of the final section. Re-sync Apt X Blue.

---

## TASK-258 — Quit is Ctrl+Q only

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | A stray `q` must not exit mid-sync |
| Verification | ruff ✓ ruff format ✓ pytest 295 passed / 4 skipped |

App binding is `ctrl+q`; footer shows `^Q`.

---

## TASK-259 — Backup bar, then sync bar

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | One bar + ETA for backup, then a new bar + ETA for the whole sync |
| Verification | ruff ✓ ruff format ✓ pytest 297 passed / 4 skipped |

Backup reports bytes so the bar can estimate time. Sync does not reset between index, analysis, and crates.

---

## TASK-261 — Progress screen: playlist + titles

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Center the bar, show the current playlist `x/x`, log song titles |
| Verification | ruff ✓ ruff format ✓ pytest 299 passed / 4 skipped |

---

## TASK-264 — Progress bar sits in the middle of the screen

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Vertically and horizontally center status + bar + playlist |
| Verification | ruff ✓ ruff format ✓ pytest 299 passed / 4 skipped |

Same `CenterMiddle` + nested `Center` pattern as Home. The log stays hidden until the first track so backup is a true mid-screen bar.

---

## TASK-265 — Keep the progress bar mid-screen when the log appears

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Status + bar + playlist stay mid-screen; log docks at the bottom |
| Verification | ruff ✓ ruff format ✓ pytest 299 passed / 4 skipped |

TASK-264 put the log inside `CenterMiddle`, so the growing track list pulled the bar to the top during sync.

---

## TASK-266 — Center the progress bar horizontally

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Full-width bar row so the 60% bar is actually centered |
| Verification | ruff ✓ ruff format ✓ pytest 299 passed / 4 skipped |

The bar's `Center` had been shrink-wrapping to the ProgressBar default, so a short bar sat on the left of the status text.

---

## TASK-267 — Bare q shows a use-^Q-to-quit popup

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Pressing `q` shows a popup that quit is `^Q` |
| Verification | ruff ✓ ruff format ✓ pytest 300 passed / 4 skipped |

---

## TASK-268 — Stretch the visible progress strip to the bar width

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | The inner `Bar` fills the 60% ProgressBar, not Textual's 32-cell default |
| Verification | ruff ✓ ruff format ✓ pytest 300 passed / 4 skipped |

TASK-266 sized the ProgressBar widget. The painted strip is a child `Bar` with `width: 32`.

---

## TASK-269 — Bare q uses Textual notify toast

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Pressing `q` shows Textual's built-in toast, not a custom modal |
| Verification | ruff ✓ ruff format ✓ pytest 299 passed / 4 skipped |

---

## TASK-270 — Shorter quit toast

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Toast says "Press ^Q to quit" and shrinks to the message |
| Verification | ruff ✓ ruff format ✓ pytest 299 passed / 4 skipped |

---

## TASK-271 — Grow MP3 ID3 when Serato frames do not fit

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Tight Rekordbox tags grow so BeatGrid/Markers2 can be written |
| Verification | ruff ✓ ruff format ✓ pytest 301 passed / 4 skipped |

A file in Untagged failed because new frames exceeded ID3 padding. Growing is allowed on MP3s with no `Serato Offsets_`. WAV still must fit in place.

---

## TASK-262 — Done screen lists failures + error.log

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Scrollable title / path / reason on Done; same lines in host `error.log` |
| Verification | ruff ✓ ruff format ✓ pytest 306 passed / 4 skipped |

---

## TASK-272 — ID3v2.2 GEO read/write

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Read and write Serato frames on ID3v2.2 MP3s |
| Verification | ruff ✓ ruff format ✓ pytest 309 passed / 4 skipped |

WONSIN `error.log` (`20260829T075133Z`) refused Memories and Humble with `'Serato BeatGrid' did not read back as written`. Both files are ID3v2.2 (`GEO`, 6-byte headers). The writer only understood v2.3/v2.4 `GEOB`.

---

## TASK-273 — Done: drop Esc Quit, center summary

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Remove Esc Quit from Done; put the completion message in the middle |
| Verification | ruff ✓ ruff format ✓ pytest 311 passed / 4 skipped |

---

## TASK-274 — Reuse unchanged backup

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Skip a new backup directory when the latest one still matches |
| Verification | ruff ✓ ruff format ✓ pytest 315 passed / 4 skipped |

---

## TASK-275 — Content-addressed incremental backups

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Store each artifact once; a new snapshot only adds what changed |
| Verification | ruff ✓ ruff format ✓ pytest 316 passed / 4 skipped |

---

## TASK-276 — ETA from recent rate, reset on phase

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Stop the progress ETA climbing as slower work starts |
| Verification | ruff ✓ ruff format ✓ pytest 317 passed / 4 skipped |

---

## TASK-263 — AIFF / AIF / M4A Serato tags

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | `read_geob` / `write_geob` for `.aif` / `.aiff` and `.m4a` / `.mp4` |
| Verification | ruff ✓ ruff format ✓ pytest 331 passed / 4 skipped |

AIFF/AIFC store ID3 GEOB in a big-endian `ID3 ` chunk; audio is `SSND` after its 8-byte header. A file with no tag gets a chunk. M4A/MP4 use `----:com.serato.dj` atoms (`beatgrid`, `markersv2`, `markers`); `mdat` stays identical and `stco`/`co64` move when `moov` grows. Serato still wants a `markers` atom for the first five cues; sync writes Markers2 only.

---

## TASK-277 — Skip GEOB rewrite when payload already matches

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Do not rewrite a file whose BeatGrid/Markers2 already match |
| Verification | ruff ✓ ruff format ✓ pytest 333 passed / 4 skipped |

`write_geob` compares intended payloads to the frames already on disk. A full match with nothing to remove returns False and does not replace the file. Sync only increments grid/cue/index counts when a rewrite happened. Progress still ticks; backup is unchanged.

---

## TASK-278 — Skip backup hash when size and mtime match

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Do not SHA-256 a live file whose size and mtime still match the snapshot |
| Verification | ruff ✓ ruff format ✓ pytest 336 passed / 4 skipped |

Same change-detection rule as rsync and restic. Inode is not used. Older snapshots without `original_mtime_ns` are hashed once; the mtime is then written onto that snapshot.

---

## TASK-279 — Remove backup and rollback

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Delete the backup and rollback system; writes proceed immediately |
| Verification | ruff ✓ ruff format ✓ pytest 285 passed / 4 skipped |

`create_backup`, `WriteContext`, rollback, and host audio-delta snapshots are gone. Sync, bootstrap, and migration write immediately. Progress starts on index/analysis/crates. `error.log` stays on the host under `~/.local/share/usbversal/<volume>/`. Recovery is restoring the Rekordbox USB.

---

## TASK-280 — Stable phase-average ETA

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Estimate remaining time from the whole current phase, not the last few items |
| Verification | ruff ✓ ruff format ✓ pytest 285 passed / 4 skipped |

The 8-sample window made ETA climb and drop as skip and rewrite tracks interleaved. Rate is now units completed since the phase started, over elapsed time since then. The progress screen still starts a new tracker when the phase changes.

---

## TASK-281 — Parallel analysis tag writes

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Write analysis tags on several tracks at once |
| Verification | ruff ✓ ruff format ✓ pytest 290 passed / 4 skipped |

ANLZ reads and GEOB rewrites run in a pool of 4 threads (cap 8; `USBVERSAL_SYNC_WORKERS` overrides). Rekordbox objects stay on the dedicated thread. Index append, crate writes, and `location.sqlite` stay sequential.

---

## TASK-282 — Write the volume parent crate file

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Write a real thumbdrive-named parent crate that wraps every synced child playlist |
| Verification | ruff ✓ ruff format ✓ pytest 291 passed / 4 skipped |

Sync writes an empty `{volume}.crate` (the mount folder name) and lists it first in `neworder.pref`. Children stay `{volume}%%…`. Rekordbox folder ancestors still have no empty files of their own.

---

## TASK-283 — Normal-width slash in crate names

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Encode `/` in crate names as a normal-width slash lookalike, and drop leftover fullwidth files |
| Verification | ruff ✓ ruff format ✓ pytest 293 passed / 4 skipped |

A real `/` cannot live in a `.crate` filename. U+2215 division slash (`∕`) replaces the TASK-254 fullwidth solidus so Serato does not show `／`. A re-sync deletes the old file and drops that spelling from `neworder.pref`.

---

## TASK-284 — Serato's slash escape in crate names

| Field | Value |
|-------|-------|
| Completed | 2026-08-29 |
| Objective | Encode `/` in crate names the way Serato does when you type a slash |
| Verification | ruff ✓ ruff format ✓ pytest 293 passed / 4 skipped |

A Serato rename on WONSIN wrote `Dance-pop ␛␛2f Dancehall` (U+241B twice + hex `2f`). Sync now uses that. Leftover `／` and `∕` files are removed on write.

---

## TASK-285 — Fix hot-cue colours and write Markers_

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Fix hot-cue colours (PCP2 RGB at offset 29) and write Markers_ so Serato pads are not leftover |
| Verification | ruff ✓ ruff format ✓ pytest 295 passed / 4 skipped |

72-byte PCP2 RGB is at offset 29. Sync rewrites `Markers_` for the first five pads because Serato prefers that tag over Markers2 when it is present.

---

## TASK-286 — Do not leave a 0-byte song after a failed replace

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | A failed audio replace must not leave a 0-byte song |
| Verification | ruff ✓ ruff format ✓ pytest 299 passed / 4 skipped |

`write_geob` fsyncs the sibling `.tmp` and writes the original bytes back if replace leaves a short file. Empty and half-size rebuilds are refused. See `docs/workflows/audio-commit.md`.

---

## TASK-287 — Fsync crate, database V2, and neworder writes

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Persist crate, database V2, and neworder with fsync; treat a 0-byte database as missing |
| Verification | ruff ✓ ruff format ✓ pytest 305 passed / 4 skipped |

`replace_flushed` is the commit path for crate, database V2, and `neworder.pref`. A zero-byte `database V2` is not a library, so bootstrap can recreate the header after a dirty unmount. See `docs/workflows/audio-commit.md`.

---

## TASK-288 — Skip leftover 0-byte crates when reading

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Library screen must not crash on a leftover 0-byte crate |
| Verification | ruff ✓ ruff format ✓ pytest 308 passed / 4 skipped |

`read_crate_track_paths` returns no tracks for an empty or unparseable `.crate`. The Library tree treats that crate as missing so a dirty-unmount leftover cannot take the TUI down.

---

## TASK-289 — List `%%` ancestor stems in `neworder.pref`

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | List every `%%` ancestor in `neworder.pref` so Serato can show nested crates |
| Verification | ruff ✓ ruff format ✓ pytest 312 passed / 4 skipped |

A working WONSIN `neworder.pref` listed `Gigs` and `Gigs%%Played` with no matching `.crate` files. Sync now inserts those folder stems before each leaf.

---

## TASK-290 — Flush the USB filesystem at the end of sync

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Flush leftover FAT and directory pages after sync; do not unmount |
| Verification | ruff ✓ ruff format ✓ pytest 316 passed / 4 skipped |

`flush_mount` is `syncfs` (or `sync`) on the mount directory. `replace_flushed` also fsyncs the parent directory. The TUI does not eject. See `docs/workflows/volume-flush.md`.

---

## TASK-291 — Portable volume flush after sync

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Flush the volume with the OS-native call; fsync audio after replace |
| Verification | ruff ✓ ruff format ✓ pytest 321 passed / 4 skipped |

Linux: `os.syncfs` or libc `syncfs`, then `BLKFLSBUF`. macOS: `F_FULLFSYNC`. Windows: `FlushFileBuffers` on `\\.\E:`. No extra package. The TUI does not unmount. See `docs/workflows/volume-flush.md`.

---

## TASK-292 — q shows the same quit toast as ^C

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Bare `q` uses Textual's `help_quit` toast, same as `^C` |
| Verification | ruff ✓ ruff format ✓ pytest 322 passed / 4 skipped |

`action_quit_hint` calls `action_help_quit`. Title is "Do you want to quit?"; body is "Press **ctrl+q** to quit the app". The compact custom toast CSS is gone.

---

## TASK-293 — Create ID3 on tagless MP3 and WAV

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Create an ID3 tag on tagless MPEG MP3 and WAV so analysis can write |
| Verification | ruff ✓ ruff format ✓ pytest 326 passed / 4 skipped |

A raw MPEG file (frame sync at byte 0) gets an ID3v2.4 tag prepended. A WAVE with no `id3 ` chunk gets one appended. Audio payload is unchanged. Junk RIFF that is not WAVE is still rejected.

---

## TASK-294 — M4A markers layout and AAC encoder delay

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Write M4A `markers` in Serato's MP4 layout and subtract AAC encoder delay |
| Verification | ruff ✓ ruff format ✓ pytest 331 passed / 4 skipped |

Serato ignores ID3-shaped Markers_ on M4A. Pads 1-5 need the 279-byte MP4 row layout. Rekordbox times include AAC priming; sync subtracts iTunSMPB or 2112 samples. See `docs/workflows/m4a-markers.md`.

---

## TASK-295 — In-place tag write when file size is unchanged

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Patch only the changed bytes when a tag rewrite does not change file size |
| Verification | ruff ✓ ruff format ✓ pytest 334 passed / 4 skipped |

Same-size GEOB writes (padded MP3 / existing WAV `id3 `) seek, write the dirty span, and fsync. No sibling `.tmp`, no `replace`. A failed patch restores that span. Size-changing writes keep the TASK-286 tmp path. See `docs/workflows/audio-commit.md`.

---

## TASK-296 — Append an id3 chunk on tagless WAV

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Append an id3 chunk on tagless WAV instead of rewriting the file |
| Verification | ruff ✓ ruff format ✓ pytest 337 passed / 4 skipped |

A WAVE with no `id3 ` chunk patches the RIFF size and appends the chunk. The `data` chunk is not rewritten. A failed append restores the original size and header. See `docs/workflows/audio-commit.md`.

---

## TASK-297 — Read only the tag to decide already on disk

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Read only the tag when deciding a GEOB write is already on disk |
| Verification | ruff ✓ ruff format ✓ pytest 340 passed / 4 skipped |

`read_geob` and the `write_geob` skip path seek past WAV `data`, MPEG frames, AIFF `SSND`, FLAC audio, and MP4 `mdat`. A rewrite still loads the whole file. See `docs/workflows/audio-commit.md`.

---

## TASK-298 — Overlap crate writes with the analysis pool

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Overlap crate writes with the analysis worker pool |
| Verification | ruff ✓ ruff format ✓ pytest 341 passed / 4 skipped |

The analysis pool starts first. Crates and `neworder.pref` write on the Rekordbox thread while tags run. `location.sqlite` waits for the tag results.

---

## TASK-299 — Fix M4A hotcue transfer and do not colour the track

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Stop M4A sync from colouring the Serato track; write cue RGB only into cue rows |
| Verification | ruff ✓ ruff format ✓ pytest 347 passed / 4 skipped |

The MP4 `markers` footer is the track colour (`00` + RGB). TASK-294's 7-byte leftover tail parsed as `#00FFFF` and filled the jog cyan. Writes now use Mixxx's unset footer `00 FF FF FF`. Markers2 `COLOR` is forced white. Rekordbox `#00C4FF` / `#FF0017` map to Serato `#0088CC` / `#CC0044` on M4A (cue RGB mapping superseded by TASK-300). See `docs/workflows/m4a-markers.md`.

---

## TASK-300 — Write Rekordbox cue RGB on M4A; keep the track uncoloured

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Write Rekordbox cue RGB on M4A the same way as MP3; keep the track uncoloured |
| Verification | ruff ✓ ruff format ✓ pytest 346 passed / 4 skipped |

M4A pads use ANLZ RGB as-is (ADR 0008), not Lexicon's Serato palette. The MP4 `markers` footer and Markers2 `COLOR` stay `00 FF FF FF` so the jog is not painted. See `docs/workflows/m4a-markers.md`.

---

## TASK-301 — Read PCP2 cue RGB after the UTF-16 comment

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Read PCP2 cue RGB after the UTF-16 comment, not from inside it |
| Verification | ruff ✓ ruff format ✓ pytest 347 passed / 4 skipped |

Named cues store a length-prefixed UTF-16 comment at offset 24. RGB is at 29 plus that length. `1.1Bars` was read as `#31002E`; the real colour is `#FF0017`. See `docs/workflows/cue-colour-offset.md`.

---

## TASK-302 — Do not create `location.sqlite`

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Record that Serato authors `location.sqlite`; we never create or insert |
| Verification | Docs only |

Serato creates the 16-table file on first open from `database V2`. Insert is not needed: new `otrk` rows are imported on the next open. We only UPDATE `bpm` / `key` on existing `asset` rows. See [serato-schema-notes.md](../schemas/serato-schema-notes.md).

---

## TASK-252 — Library two-pane window

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Playlists left with coloured `x/y` and no `-`; track preview right |
| Verification | ruff ✓ ruff format ✓ pytest 351 passed / 4 skipped |

Left pane is the playlist tree plus a traffic-light legend. Right pane is a sortable Title / Genre / Key / BPM table for the highlighted playlist. Unselected rows have a blank checkbox, not `-`. Track colour is crate membership (green / red). Analysis-aware yellow is TASK-303.

---

## TASK-304 — Library pane polish

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Narrower Playlists pane, round borders, lined legend, no sideways table scroll |
| Verification | ruff ✓ ruff format ✓ pytest 352 passed / 4 skipped |

Playlists is one third, Tracks two thirds. Both panes use `border: round`. The legend is three coloured dots under a rule. Long titles (and playlist names) clip with an ellipsis so Genre / Key / BPM stay on screen.

---

## TASK-305 — Readable playlist tree names

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Nested playlist names stay readable; clip from the live tree width |
| Verification | ruff ✓ ruff format ✓ pytest 353 passed / 4 skipped |

TASK-304's 16-cell name column plus tree guides left depth-3 folders as a
single letter. Names now take `tree.size.width − count − gutter`, the
Playlists pane is `2fr` with `min-width: 48`, and labels refresh on
resize. Track-table title clipping is unchanged.

---

## TASK-306 — Legend rule and coloured words

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Drop the legend rule one row; colour the words to match the dots |
| Verification | ruff ✓ ruff format ✓ pytest 354 passed / 4 skipped |

The rule is the legend's top border. A one-cell top margin drops it off
the tree. Each label is the same green / yellow / red as its bullet.

---

## TASK-307 — Flatten tree; status beside mount

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Drop the All playlists parent; `a` selects all; status beside the mount |
| Verification | ruff ✓ ruff format ✓ pytest 354 passed / 4 skipped |

Top-level folders sit on the hidden Tree root so they are not indented
under a synthetic parent. `a` toggles the whole library. The selection
count shares the header with the mount path, which frees the row under
the panes.

---

## TASK-308 — Legend flush under the rule

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Remove the blank row between the legend rule and the labels |
| Verification | ruff ✓ ruff format ✓ pytest 354 passed / 4 skipped |

The rule stays one cell below the tree (`margin-top: 1`). Padding under
the rule is 0 so synced / partial / not synced start on the next row.

---

## TASK-309 — ^a / ^q, hide tree scrollbar, native table

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | `^a` Select All, `^q` Quit, no playlist scrollbar, native track table |
| Verification | ruff ✓ ruff format ✓ pytest 355 passed / 4 skipped |

The tree scrollbar covered `x/y`. It is hidden; arrows still move. The
track table drops zebra stripes and the themed header so it matches the
tree's terminal colours. Row text is still traffic-light by crate state.

---

## TASK-310 — Tree flush to legend; visible parent guides

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Drop the gap above the legend; keep parent │ on the cursor row |
| Verification | ruff ✓ ruff format ✓ pytest 356 passed / 4 skipped |

The legend's top margin ate a tree row. Textual paints selected guides
the same colour as the cursor bar, so the parent line vanished on a
crate. Guides now stay `ansi_default` on the cursor.

---

## TASK-311 — Light path to a crate and children of a folder

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Cursor on a crate lights the parent path; a folder still lights every child |
| Verification | ruff ✓ ruff format ✓ pytest 358 passed / 4 skipped |

Textual only lit guides under a selected folder. `PlaylistTree` also
lights the ancestor chain when the cursor is on a crate, and still
lights every child when the cursor is on a folder.

---

## TASK-312 — Grow a WAV id3 chunk that sits after data

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Grow a tight WAV `id3 ` after `data` without moving the audio stream |
| Verification | ruff ✓ ruff format ✓ pytest 362 passed / 4 skipped |

Heaven Is A P.wav failed with "growing the tag would move the audio
stream" while `id3 ` sat after `data` and only a `LIST` followed it.
That layout may grow. The commit rewrites the metadata tail only. An
`id3 ` before `data` still refuses.

---

## TASK-313 — Posting amber instead of TUI green

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Replace TUI green with Posting amber; brighter yellow on footer keys |
| Verification | ruff ✓ ruff format ✓ pytest 363 passed / 4 skipped |

Synced counts, the legend, progress lines, the Done summary, and the
progress bar use `#f0b429`. Footer shortcut keys use `#ffd700`. Partial
and error stay yellow and red.

---

## TASK-314 — Amber on pane borders only

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Restore traffic-light green; amber only on the Library pane boxes |
| Verification | ruff ✓ ruff format ✓ pytest 363 passed / 4 skipped |

TASK-313 painted synced / progress / Done amber. Those go back to green.
The Posting yellow is the round border (and title) on Playlists and
Tracks. Footer keys stay `#ffd700`.

---

## TASK-303 — Analysis-aware track colour and honest x/y

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Yellow when a track is in the crate but Rekordbox analysis is not on the file; count only green tracks in `x/y` |
| Verification | ruff ✓ ruff format ✓ pytest 369 passed / 4 skipped |

Red is not in the crate. Yellow is in the crate, but ANLZ beats or cues
are not on the file. Green is in the crate and those frames are present,
or Rekordbox had nothing to port. Playlist colour is the same three-way
fold as before; the numerator is the green count.

---

## TASK-315 — Report missing audio as an analysis error

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | A missing audio file with Rekordbox analysis to port shows on Done, not as a silent skip |
| Verification | ruff ✓ ruff format ✓ pytest 371 passed / 4 skipped |

`safety day 24sep2025` stayed yellow with no TUI error because
`She Will Be Loved (Didot Flip)` is in Rekordbox (ANLZ present) but the
MP3 is not on the stick. Sync treated that as nothing happened.

---

## TASK-316 — Mark existing location.sqlite rows analyzed

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | When `location.sqlite` exists, set `analysis_flags` to 31 on synced tracks with a beatgrid |
| Verification | ruff ✓ ruff format ✓ pytest 372 passed / 4 skipped |

The library-list unanalyzed count is this bitmap, not the file tags.
First open still imports from `database V2` with the flag unset. A
second sync, after Serato has created the file, marks the rows.

---

## TASK-317 — Library paints before analysis colours finish

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Do not keep the Home scan bar on screen while Library reads ANLZ and tags |
| Verification | ruff ✓ ruff format ✓ pytest 375 passed / 4 skipped |

`on_screen_resume` used to await every analysis-ported check, so Home
stayed up with a frozen scan bar. The tree now appears from crate
membership; colours follow. Highlighting a crate no longer cancels
that worker.

---

## TASK-318 — Checking analysis stays on Home with a moving scan bar

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Keep the Home scan bar moving with "Checking analysis" until Library is ready |
| Verification | ruff ✓ ruff format ✓ pytest 376 passed / 4 skipped |

Analysis colours are computed on Home after the USB opens. The spinner
stays the active screen, so it keeps ticking. Library is handed the
finished tree and paints once.

---

## TASK-319 — Show Checking analysis on the Home detecting screen

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Show Checking analysis on the first Home screen as well as after open |
| Verification | ruff ✓ ruff format ✓ pytest 376 passed / 4 skipped |

Detecting and opening keep their own line; Checking analysis sits
underneath so the banner screen shows it from the start.

---

## TASK-320 — Checking analysis is a single Home phase caption

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Checking analysis replaces the Home status line as phase 3 |
| Verification | ruff ✓ ruff format ✓ pytest 376 passed / 4 skipped |

Not a second line under detecting or opening. Same banner and scan
bar; the caption steps SEARCHING, then OPENING, then CHECKING.

---

## TASK-321 — Show the Home scan bar in the Library Tracks pane while loading

| Field | Value |
|-------|-------|
| Completed | 2026-08-30 |
| Objective | Same sweeping scan bar on the right while the track list is loading |
| Verification | ruff ✓ ruff format ✓ pytest 377 passed / 4 skipped |

`ScanBar` is shared with Home. The Tracks pane centers it until
preview rows are ready, then shows the table.

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
