# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-27

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-076` |
| Objective | Stop a plain rekordbox stick (no `_Serato_` at all) from being a dead end — `sync_playlists` and friends currently just raise `SeratoLibraryRequiredError` and stop |
| Completed | 2026-08-27 |

### Scope

Files touched:

- `app/adapters/serato/paths.py` — `serato_root_for()` and `database_v2_path()`
  added, computing where `_Serato_`/`database V2` belong even when neither
  exists yet; `resolve_serato_library` refactored to use them
- `app/adapters/serato/writer.py` — `create_empty_database_v2()`: writes just
  the `vrsn` header (`"2.0/Serato Scratch LIVE Database"`, [verified] in the
  schema notes) — what a fresh Serato install has before anything is
  imported. Explicitly documented as **never** to be called when a database
  V2 already exists (merge, never regenerate, is non-negotiable for a real
  vendor index).
- `app/services/bootstrap_service.py` (new) — `bootstrap_serato_library()`:
  a no-op (reports `created=False`) when a Serato library already exists;
  otherwise backs up the Rekordbox files, then creates `_Serato_/`,
  `Subcrates/`, an empty `database V2`, and an empty `neworder.pref`
- `app/storage/backup.py` — `create_backup` now disambiguates an auto-generated
  `backup_id` collision (its timestamp has one-second resolution) with a
  counter suffix instead of raising `FileExistsError`; an explicitly-passed
  `backup_id` still raises on collision, since that's caller intent. Found
  because chaining bootstrap straight into `sync_playlists` in the same test
  process hit exactly this collision — not a hypothetical.
- `app/tui/screens/home.py` — `_open()` now calls `bootstrap_serato_library`
  before `open_library`, so a rekordbox-only stick reaches the Library screen
  (and can actually sync) through the TUI, not just through direct calls
- `tests/test_bootstrap.py` (new) — six tests: creates a valid empty library,
  `PIONEER/` is byte-identical after (hashed, not just "should be"), the
  backup actually contains the Rekordbox files, an existing Serato library is
  left completely alone, no Rekordbox files means no backup means
  `FileNotFoundError`, and — the actual point — `sync_playlists` succeeds on
  a stick that had no Serato library five lines earlier
- `tests/test_backup.py` — two new tests for the collision fix: a forced
  same-second collision gets a `-2` suffix, an explicit `backup_id` collision
  still raises
- `tests/test_tui_home.py` — three existing tests patch
  `bootstrap_serato_library` alongside `probe_mount`/`open_library` (it runs
  unconditionally now); one new test lets bootstrap run for real against a
  rekordbox-only stick and checks the files land on disk
- `docs/planning/serato-index-bootstrap.md`, `docs/tasks/backlog.md`,
  `docs/state/*.json`

### Design decisions

- **Bootstrap is a strict no-op on an existing library, not a merge point.**
  `merge_never_regenerate_vendor_index` is a hard rule for a *real* index;
  bootstrap's whole job is filling the gap when there is no index at all, so
  the moment one exists — even a nearly-empty one — it backs off entirely
  rather than trying to reconcile anything.
- **Backs up Rekordbox files, not Serato files, before writing.** There is
  nothing under `_Serato_` to back up yet (that's the premise), and the
  safety property this task calls for is proving `PIONEER/` stays untouched
  — the backup is *of* the thing that must not change, which also gives
  `WriteContext` something non-empty to validate against.
- **Wired into the TUI immediately, not left as a standalone function.**
  Consistent with this whole session: `HomeScreen` already treats a
  rekordbox-only stick as valid (it never required `probe.has_serato`), so
  without this wiring the Library screen would render fine and then Progress
  would fail on `SeratoLibraryRequiredError` the moment someone pressed enter
  — a gap that would only be found by someone actually trying to use it.
- **The backup-id collision fix is in scope, not deferred.** It surfaced
  directly from testing this task's own integration path (bootstrap's backup
  and `sync_playlists`'s backup landing in the same second) rather than being
  speculative, and AGENT.md's non-negotiable backup-before-write rule means a
  spurious `FileExistsError` there is a real correctness bug, not cosmetic.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 235 passed, 4 skipped (no stick mounted, no `dist/usbversal` built; skips are 2 `/mnt/usb` integration tests, the opt-in full PyInstaller build, and the binary-help smoke test) |
| `.venv/bin/python -m app.cli --help` | unchanged |

## Next

`TASK-090` (`export.pdb` DeviceSQL reader) is the only item left in
`docs/tasks/backlog.md`'s active queue, and it's explicitly marked deferred:
"Not needed while `exportLibrary.db` is present — only for older sticks that
ship `export.pdb` alone." Its own verification step ("dump the playlist tree
and check names are readable") needs a real classic-format stick, which
isn't available this session. Everything else queued at the start of this
session — the analysis-port finish line (TASK-130-134), all of M11's
interactive TUI (TASK-200-208), and the remaining M8 items (TASK-075,
TASK-076) — is done.
