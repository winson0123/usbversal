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

## Template (for future entries)

```markdown
## TASK-XXX — Title

| Field | Value |
|-------|-------|
| Completed | YYYY-MM-DD |
| Commit | `<hash>` |
| Verification | ruff ✓ pytest ✓ |
```
