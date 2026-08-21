# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-21

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-070` |
| Objective | Capture externally verified Serato write formats into the docs system and re-plan Stage 1 / Stage 2 |
| Completed | 2026-08-21 |

### Scope

Documentation and planning only — **no application code changed**.

Files touched:

- `docs/schemas/serato-schema-notes.md` (rewritten — verified formats)
- `docs/schemas/rekordbox-schema-notes.md` (appended — `export.pdb`, ANLZ)
- `docs/decisions/0007-revive-analysis-sync-on-verified-formats.md` (new)
- `docs/decisions/0006-serato-analyzed-and-beatgrid-tags.md` (marked superseded)
- `docs/planning/serato-index-bootstrap.md` (new — Stage 1)
- `docs/planning/rekordbox-to-serato-analysis-sync.md` (deferred → planned)
- `docs/planning/rekordbox-to-serato-playlist-migration.md` (open questions answered)
- `docs/adapters/serato.md` (schema + write status)
- `docs/tasks/backlog.md` (re-planned; M8/M9/M10 added)
- `docs/state/*.json`
- `tests/fixtures/serato/` (new — ground-truth WAV pair + README)

### Source

An external agent's handoff, delivered as an untracked working directory and
**deleted after capture by request**. Its Part A findings were reproduced
locally before capture:

- Decoding `Techno1.BEFORE.wav` vs `Techno1.AFTER.wav` yields exactly the
  documented diff — two `CUE` entries appear in `Serato Markers2`
  (`slot=0 pos=0ms #CC0044`, `slot=1 pos=441ms #0088CC`), while
  `Serato BeatGrid` and `Serato Autotags` are byte-identical.
- `test.crate`, `database-V2-local`, and `neworder.pref` decoded to the
  documented structures; their decoded content is transcribed into
  `serato-schema-notes.md`.
- A crate written by usbversal's own `write_crate` was dumped and confirmed
  structurally valid (correct `ptrk` form, order preserved; `ovct` column set
  differs from Lexicon's, which is cosmetic).

Only the two WAV fixtures were retained, at the user's direction.

### Key findings driving the re-plan

1. **usbversal cannot bootstrap.** `migrate-playlist` matches against the
   existing Serato index and raises `SeratoLibraryRequiredError` when `_Serato_`
   is absent, so on a plain rekordbox stick it does nothing. → M8.
2. **`neworder.pref` is neither written nor backed up** — a live rollback gap.
   → TASK-071.
3. **ADR 0006's conclusion is superseded.** The analyzed gate is satisfied by
   real hot cues; the earlier failure was synthetic anchor cues. → ADR 0007, M9.
4. Nested playlist folders collide on the leaf name. → TASK-075.
5. **`otrk` fields are sparse on real data.** Confirmed on `/mnt/usb`: `talb`
   appears on 299/793 records, `tlen` on 183, and `udsc` appears at all despite
   being absent from the handoff's field list. A writer must not assume a fixed
   record shape. This was not visible from the WAV fixture alone.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | **fail — 4 files**, all pre-existing and untouched here (see TASK-091) |
| `.venv/bin/pytest` | 89 passed, 1 skipped (USB mounted this run, so 2 integration tests ran) |
| `.venv/bin/python -m app.cli --help` | all commands listed |
| Markers2 fixture decode | BEFORE 30 B / AFTER 72 B, matches documented layout |
| `/mnt/usb` format re-validation | `database V2` 793 `otrk`, `neworder.pref` 84 B, `Pocket.crate` 80 `otrk` — all decode per spec |
| Doc relative links | 1 broken, pre-existing (`release-workflow.md` → `../packaging/usbversal.spec`) |

`ruff format --check` failed before this task and is untouched by it — the diff
is documentation plus binary fixtures. Fixing it is TASK-091, kept as a separate
commit per AGENT.md ("do not batch unrelated changes").

## Next

`TASK-071` (backup `neworder.pref`) — smallest safety-relevant unit, and a
precondition for every other Stage 1 write.
