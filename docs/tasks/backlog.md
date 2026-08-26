# Task Backlog

Queued work. **Only one task may be active** — see [`AGENT.md`](../../AGENT.md).

Priority order (top first). Decompose before starting if scope exceeds one commit.

---

## M1 — Project Foundation

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-001`~~ | ~~Add `pyproject.toml` and package skeleton~~ | Done |
| ~~`TASK-002`~~ | ~~Configure ruff, pytest, dev dependencies~~ | Done — `pyproject.toml` |
| ~~`TASK-003`~~ | ~~CLI entrypoint stub~~ | Done — `app/cli/main.py` |

## M2 — Storage Layer

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-010`~~ | ~~Mount path validation utilities~~ | Done — `storage.mounts.resolve_mount_path`. The old note ("no auto-detect yet") was wrong; auto-detect shipped with TASK-050. |
| ~~`TASK-011`~~ | ~~Backup copy + manifest.json~~ | Done |
| ~~`TASK-012`~~ | ~~Rollback from manifest~~ | Done — `rollback` CLI |

## M3 — Core Domain

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-020`~~ | ~~Domain models (Library, Playlist, Track)~~ | Done — `app/core/domain.py` |
| ~~`TASK-021`~~ | ~~Adapter protocol + WriteContext~~ | Done |
| ~~`TASK-022`~~ | ~~Event types and bus skeleton~~ | Done |

## M4 — Adapters

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-030`~~ | ~~Rekordbox detect + read-only list~~ | Done |
| ~~`TASK-031`~~ | ~~Serato detect + read-only crates~~ | Done |
| ~~`TASK-032`~~ | ~~Rekordbox write path~~ | **Dropped 2026-08-21.** Contradicts the mission: rekordbox owns `PIONEER/` and stays untouched, which is what makes the two-index approach lossless. No consumer, and building it would undermine the safety story. |

## M5 — Jobs

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-040`~~ | ~~JobRunner + registry~~ | Done |
| ~~`TASK-041`~~ | ~~Scan job~~ | Done |
| ~~`TASK-042`~~ | ~~Cancel + resume metadata~~ | Done |

## M6 — CLI Commands

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-050`~~ | ~~`scan` command~~ | Done |
| ~~`TASK-051`~~ | ~~`list-playlists` / `list-crates`~~ | Done |
| ~~`TASK-052`~~ | ~~`backup` / `rollback`~~ | Done |
| ~~`TASK-053`~~ | ~~`apply` with plan file~~ | Removed in TASK-109; superseded by `sync_playlists` |

## M7 — Packaging & Validation

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-060`~~ | ~~PyInstaller spec + smoke test~~ | Done |
| ~~`TASK-061`~~ | ~~`/mnt/usb` integration validation~~ | Done |
| ~~`TASK-070`~~ | ~~Capture verified Serato write formats; re-plan Stage 1/2~~ | Done — this backlog |

---

## M8 — Serato Index Authoring (Stage 1)

Makes a **rekordbox-only stick readable by Serato**. Writes only inside
`_Serato_/`; never touches `PIONEER/` or the audio under `Contents/`.
Plan: [serato-index-bootstrap.md](../planning/serato-index-bootstrap.md).
Formats: [serato-schema-notes.md](../schemas/serato-schema-notes.md).

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-071`~~ | ~~Add `neworder.pref` to the Serato backup set~~ | Done — TASK-114 added it to `serato_files_on_mount` |
| ~~`TASK-073`~~ | ~~`database V2` append writer~~ | Done — TASK-112. A Rekordbox-to-`otrk` field mapper is still outstanding and moves to TASK-113. |
| ~~`TASK-113`~~ | ~~Rekordbox metadata → `otrk` fields~~ | Done — TASK-113, formats derived by diffing 793 records Lexicon wrote |
| ~~`TASK-074`~~ | ~~`neworder.pref` merge/write~~ | Done — TASK-114, `adapters/serato/neworder.py` |
| `TASK-075` | Nested playlist folders → `Parent%%Child.crate` | Current code flattens to the leaf name, so same-named playlists in different folders collide. Convention is [assumed], not verified — validate in Serato. |
| `TASK-076` | Bootstrap `_Serato_` on a rekordbox-only stick | Create `_Serato_/`, `Subcrates/`, `database V2`, `neworder.pref` where absent. Removes `SeratoLibraryRequiredError` as a dead end. Backup-gated; verify `PIONEER/` hash is unchanged. |

## M9 — Analysis Tag Sync (Stage 2)

Writes hot cues and beatgrids into the **audio files**. Requires
[ADR 0007](../decisions/0007-revive-analysis-sync-on-verified-formats.md);
supersedes the abandoned TASK-034. **Mutates user audio — explicit confirmation
plus per-file backup required.** Sequenced strictly after M8.

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-080`~~ | ~~ANLZ reader — `PQTZ` beatgrid, `PCO2` hot cues~~ | Done — TASK-115, `adapters/rekordbox/anlz.py` |
| ~~`TASK-081`~~ | ~~Rekordbox → Serato cue colour table~~ | Dropped — Rekordbox stores RGB in the ANLZ entry, so no table is needed |
| ~~`TASK-082`~~ | ~~`Serato Markers2` GEOB writer (hot cues)~~ | Done — TASK-115, byte-exact against the fixture pair |
| ~~`TASK-083`~~ | ~~`Serato BeatGrid` + `Autotags` GEOB writer~~ | Done — TASK-117/119; `Autotags` deliberately not written |
| `TASK-084` | Container tag I/O — **MP3 only; WAV done** | **MP3 is untested and is the one that matters** (a rekordbox USB is all MP3). WAV needs RIFF `id3 ` chunk rewrite + RIFF size fixup; fixtures cover WAV only. Must preserve GEOB frames it does not own. FLAC/MP4 out of scope. |
| `TASK-085` | `sync-analysis` CLI (re-introduce) | Backup-gated, idempotent, must not clobber existing Serato analysis on partially analyzed libraries. Confirm with the user before writing. |

## M10 — Deferred

| ID | Title | Notes |
|----|-------|-------|
| `TASK-090` | `export.pdb` DeviceSQL reader | Spec captured in [rekordbox-schema-notes.md](../schemas/rekordbox-schema-notes.md) but **never parsed**. Not needed while `exportLibrary.db` is present — only for older sticks that ship `export.pdb` alone. Validate by dumping the playlist tree and checking names are readable. |
| ~~`TASK-091`~~ | ~~Reconcile `ruff format` drift~~ | Done |

## M10.5 — Finish the analysis port

The adapters work and are confirmed in Serato, but no service or command calls
them. See [HANDOFF.md](../HANDOFF.md).

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-130`~~ | ~~Wire grids, cues and the library index into `sync_playlists`~~ | Done — every synced track with Rekordbox analysis now gets its beatgrid and hot cues written, and `location.sqlite` is updated for any track that got a grid. Backs up each audio file it is about to touch. No index BPM correction pass yet for the ~70 already-wrong rows (TASK-132). |
| ~~`TASK-131`~~ | ~~Move write verification into `write_geob`~~ | Done — `verify_geob_rewrite()` checks size, audio-stream hash, and frame read-back before any byte reaches disk; a failure raises `TagFormatError` and the original file is untouched. |
| ~~`TASK-132`~~ | ~~Codify the index BPM rules~~ | Done — `correct_index_bpm()` in `sync_service.py` sets every indexed track's BPM to its first beat's tempo, library-wide (not just tracks in a playlist being synced), and never inserts a row Serato does not already have. Not yet run against the real stick's ~70 wrong rows — see HANDOFF.md. |
| ~~`TASK-133`~~ | ~~Never-clobber regression test~~ | Done — `tests/test_never_clobber.py` proves `write_geob` leaves `Key`, `Energy`, `CuePoints`, and Mixed In Key's own unprefixed `BeatGrid` byte-identical across a beatgrid write, a cue write, and a removal of our own frame, and refuses (rather than evicting a foreign frame) when a write would not fit. |
| ~~`TASK-134`~~ | ~~Correct the retracted claims in `docs/`~~ | Done — TASK-126, `analysis-data-study.md` and `serato-schema-notes.md` |
| ~~`TASK-127`~~ | ~~Cover the ANLZ reader with tests~~ | Done — not originally backlogged; the reader had no direct test coverage until this pass, `tests/test_anlz.py` |

## M11 — Interactive TUI (the shipped product)

> IDs renumbered to the 200s on 2026-08-21: 110-116 had been reused by the
> write-path work and collided.

The argparse CLI is a **test harness**, not the deliverable. Plan:
[interactive-tui.md](../planning/interactive-tui.md). These gate the real tool
and none of them exist yet.

| ID | Title | Notes |
|----|-------|-------|
| ~~`TASK-200`~~ | ~~Per-playlist sync state~~ | Done — TASK-111, `playlist_sync_states()` |
| ~~`TASK-201`~~ | ~~Playlist tree model~~ | Done — `core/playlist_tree.py` (`build_playlist_tree`) nests the flat list; `sync_service.playlist_tree_sync_states` adds the per-folder rollup (green only if every descendant is synced, red only if none are, yellow otherwise; an empty folder reads red, not vacuously green). |
| ~~`TASK-202`~~ | ~~Single "valid DJ USB?" readiness verdict~~ | Done — TASK-110, `probe_mount()` returns None for an empty mount point |
| ~~`TASK-203`~~ | ~~Removable-media polling~~ | Done — `storage/mount_watch.py`'s `MountWatcher.poll()` diffs `MountScanner.list_mounts()` against the previous poll's set; one directory listing per poll, no library detection or database opens. Callers run `services.library.probe_mount` (also stat-only) on an appeared mount to check DJ USB validity. |
| ~~`TASK-204`~~ | ~~Progress rate + ETA~~ | Done — `jobs/progress_rate.py`'s `ProgressRateTracker` averages rate over the whole run (steadier than a most-recent-interval rate for variable-cost steps like tag writes) and derives an ETA when `total` is known. Wired into `CliProgressRenderer`, which now appends `(N.N/s, eta Xs)` once a job has two samples, tracked per `job_id`. |
| ~~`TASK-205`~~ | ~~Batch sync over selected playlists~~ | Done — TASK-114, `sync_playlists()` takes one backup per run |
| ~~`TASK-206`~~ | ~~TUI framework ADR + shell~~ | Done — [ADR 0009](../decisions/0009-use-textual-for-the-tui.md) picked `textual`. `app/tui/` scaffolded with `UsbversalApp` and the Home screen (steps 1-2, Waiting/Detect), reachable via `usbversal tui` / `python -m app.tui`. Verified with a real PyInstaller build whose `tui` subcommand renders headless. Decomposed from the original one-line item — see TASK-207/208 below, added at the same time so the remaining screens aren't lost to scope creep. |
| ~~`TASK-207`~~ | ~~TUI Library screen~~ | Done — `app/tui/screens/library.py`. `playlist_tree_sync_states()` feeds a `textual.widgets.Tree`; space (a **priority** binding — Tree's own default binds space to expand/collapse, which a priority binding on the Screen overrides) toggles a leaf or, on a folder, every descendant playlist at once; enter reports the selection (running the sync is TASK-208). `HomeScreen` now pushes this screen once a valid library opens. |
| ~~`TASK-208`~~ | ~~TUI Progress + Done screens~~ | Done — `app/tui/screens/progress.py`. `sync_playlists()` gained an optional `on_progress` callback (called per analysis track — the slow part of a sync); `ProgressScreen` runs it via `asyncio.to_thread` in a worker and renders `textual.widgets.ProgressBar` plus rate/ETA text from `jobs.progress_rate.ProgressRateTracker`; `DoneScreen` shows the summary (enter returns to Library, escape quits). This is the first point `sync_playlists` is reachable from the TUI at all — full Waiting → Detect → Library → Progress → Done flow verified end to end, not just per screen. |

---

## Cross-cutting notes

- **`serato_tools.usb_export.copy_crates_to_usb` `rmtree`s the destination
  `_Serato_`.** Never call it. Its own source carries a `TODO: merge with
  existing, instead of replacing`.
- Sticks in the wild already carry a real `database V2` (522 KB / 793 tracks on
  the reference stick) written by Serato or Lexicon. **Merge, never regenerate.**
- Stage 1 is independently shippable and touches no audio. Stage 2 is the risky
  half; do not let them share a commit.
- **Code carries no historical reasoning.** Why a thing is shaped the way it is
  belongs in `docs/`; the source states only what it does now.
