# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-28

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-249` |
| Objective | A leftover-character Markers2 tag must not abort the whole sync |
| Completed | 2026-08-28 |

### Scope

- `_decode_serato_b64` drops one `4n+1` leftover character; remaining decode errors return no markers.
- FLAC Serato fields use the same helper.
- Per-track `binascii.Error` is skipped, not fatal.
- Findings recorded in ADR 0010 and `serato-schema-notes.md`.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 285 passed, 4 skipped |

## Next

`TASK-250` — run `correct_index_bpm` on a real stick (backup-gated). Then variable-tempo deck check, then Library two-pane.
