# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-26

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-130` |
| Objective | Wire Rekordbox beatgrid/hot-cue writing and the `location.sqlite` index update into `sync_playlists`, so a normal sync run reproduces what was previously only demonstrated by hand |
| Completed | 2026-08-26 |

### Scope

Files touched:

- `app/services/sync_service.py` — `_sync_analysis`, `_write_track_tags`,
  `_analysis_dat_path` helpers; `sync_playlists` now runs the analysis pass
  after crate/database writes; `SyncReport` gained `grids_written`,
  `cues_written`, `index_rows_updated`, `analysis_errors`
- `app/services/backup_service.py` — `serato_files_on_mount` now includes
  `location.sqlite` when present; `backup_mount_for_migration` gained
  `extra_files` (mirrors the existing parameter on `backup_mount_libraries`)
- `tests/test_sync_playlists.py` — ANLZ/asset-table fixture builders, four new
  end-to-end tests (grid+cues+index written; no analysis data leaves the index
  alone; a malformed ANLZ file is skipped, not fatal; the audio file about to
  be tagged is captured in the run's backup)
- `tests/test_backup.py` — direct coverage for the two backup_service changes
- `docs/HANDOFF.md`, `docs/tasks/backlog.md`, `docs/state/*.json`

### Design decisions

- **Index BPM comes from the first beat's tempo**, not Rekordbox's headline
  average — this is the rule HANDOFF.md documents as correct (Rekordbox
  consistently mis-picks the section for variable-tempo tracks). Full
  correction of already-wrong rows outside this pass is TASK-132.
- **The index is only updated for a track that got a fresh grid in this
  pass.** A track with hot cues but no beatgrid, or with neither, leaves
  Serato's existing index row untouched — the point is to keep the list in
  step with what the deck now actually reads, not to guess at BPM from
  Rekordbox metadata for a file this pass never wrote to.
- **Per-track failures are caught and recorded, not fatal.** A missing audio
  file, an unreadable ANLZ container, or a tag write that does not fit the
  padding budget is appended to `SyncReport.analysis_errors` and the run
  continues — consistent with the per-operation-failure model TASK-102
  established for `apply`.
- **Only files with Rekordbox analysis data are added to the run's backup**,
  not every audio file in the synced playlists — `_analysis_dat_path` is
  checked before the backup is taken, so untouched files are not copied.
- Write verification (size/hash/read-back, abort on first anomaly) is
  deliberately **not** in this pass — that is TASK-131, scoped separately per
  AGENT.md ("do not batch unrelated changes"). `write_geob`'s existing
  same-size-tag guard is the only safety net right now.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 157 passed, 3 skipped (no stick mounted this session; skips are the two `/mnt/usb` integration tests and the PyInstaller build) |
| `.venv/bin/python -m app.cli --help` | all commands listed (unchanged — `sync_playlists` still has no CLI entry point) |

Exercised against synthetic fixtures only: `tests/fixtures/serato/Techno1.BEFORE.wav`
(a real WAV carrying real Serato GEOB frames with realistic padding) plus
hand-built ANLZ `.DAT`/`.EXT` containers. **Not yet re-run against the real
test stick** — see "Do this next" §1 in HANDOFF.md.

## Next

`TASK-131` (write verification in `write_geob`) — the next HANDOFF.md
priority, and the natural follow-on now that `write_geob` is on the path
`sync_playlists` actually runs instead of only a hand-run script.
