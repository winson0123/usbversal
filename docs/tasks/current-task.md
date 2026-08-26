# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-26

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-132` |
| Objective | Codify the index BPM rule (first beat's tempo) as a library-wide correction pass, not just something `sync_playlists` applies to tracks it happens to touch |
| Completed | 2026-08-26 |

### Scope

Files touched:

- `app/services/sync_service.py` — new `IndexCorrectionResult` dataclass and
  `correct_index_bpm()`: walks every Rekordbox content row with analysis data,
  compares its first beat's tempo against the matching `location.sqlite` row,
  and corrects the row when they disagree
- `tests/test_sync_playlists.py` — five new tests: fixes a wrong row, leaves a
  matching row alone, dry run writes nothing, a track with no existing index
  row is never inserted, missing `location.sqlite` raises
- `docs/HANDOFF.md`, `docs/tasks/backlog.md`, `docs/state/*.json`

### Design decisions

- **Library-wide, not playlist-scoped.** `sync_playlists`'s analysis pass
  (TASK-130) only touches tracks in the playlists being synced, so the ~70
  constant-tempo rows and the `Drake - NOKIA` variants HANDOFF.md names as
  still wrong would stay wrong forever if a track never happens to sit in a
  synced playlist again. `correct_index_bpm()` iterates
  `library.rekordbox.database.get_contents()` directly instead.
- **Same rule as `sync_playlists`, reused rather than reimplemented**: the
  correct BPM is the first beat's tempo from the ANLZ grid
  (`_analysis_dat_path` and `read_beats`, both already in this module). A
  constant-tempo track's first beat already equals its real tempo, so this one
  rule naturally corrects both the half/double bug and Serato's
  wrong-section picks on variable-tempo tracks, without a separate detection
  heuristic for "half or double."
- **Never touches audio.** Only the index. `update_track_analysis` already
  refuses to insert a row for a path Serato has not indexed, which is exactly
  the "never insert" rule HANDOFF.md called for — nothing new needed there.
- **Not yet run against the real stick.** The ~70 known-wrong rows are still
  wrong on `/mnt/usb` until someone runs this there — see HANDOFF.md §1.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 169 passed, 3 skipped (no stick mounted; skips are the two `/mnt/usb` integration tests and the PyInstaller build) |
| `.venv/bin/python -m app.cli --help` | all commands listed (unchanged — no CLI entry point for this yet, same as `sync_playlists`) |

## Next

`TASK-133` (never-clobber regression test) — confirm nothing this tool writes
touches the ~20% of the library carrying Mixed In Key frames or the one file
with Sound Forge frames.
