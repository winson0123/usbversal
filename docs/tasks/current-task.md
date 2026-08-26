# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-26

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-131` |
| Objective | Move write verification (size, audio-stream hash, frame read-back) into `write_geob` so every caller gets it, not just a hand-run checklist |
| Completed | 2026-08-26 |

### Scope

Files touched:

- `app/adapters/serato/tags.py` — new `_audio_span` (locates the raw audio
  payload outside the tag; WAV needs its `data` chunk specifically, not
  "everything after the tag"), `_read_geob_bytes` (in-memory GEOB parse,
  factored out of `read_geob`), public `verify_geob_rewrite` (size, audio-hash,
  and frame read-back checks), called from `write_geob` before the temp file
  is written
- `tests/test_audio_tags.py` — a new-frame round-trip test, a `remove_geob`
  round-trip test, and direct unit tests of `verify_geob_rewrite`'s four
  failure modes plus its pass-through case

### Design decisions

- **Verification runs before the temp file is written, not after.** `write_geob`
  already writes to `<path>.tmp` then atomically renames over the target; the
  new check runs on the in-memory rebuilt bytes first, so a failure leaves
  both the original file and the temp file untouched — `verify_geob_rewrite`
  never sees or touches the filesystem itself.
- **The audio-hash check is chunk-aware for WAV, not "hash everything after
  the tag".** HANDOFF.md records this as a real prior defect: a WAV's `id3 `
  chunk is not necessarily the last chunk, so hashing the tail of the file
  produced a false positive (looked unchanged when it wasn't, or flagged a
  change when there wasn't one) depending on chunk order. `_audio_span` finds
  the actual `data` chunk for WAV and reuses the existing MP3 tag-relative
  logic for MP3.
- **`verify_geob_rewrite` is public**, not a private helper, so it is
  independently testable against synthetic before/after byte strings the way
  `encode_beatgrid` and the ANLZ reader already are, and so a future caller
  that assembles bytes itself (rather than going through `write_geob`) can
  reuse the same safety check.
- Only GEOB frames are covered — `remove_frames` (arbitrary non-GEOB ID3
  frame ids) is unchanged and unverified beyond the existing size guard,
  since the incident this task responds to was specifically about Serato's
  own GEOB frames failing to round-trip.

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 164 passed, 3 skipped (no stick mounted; skips are the two `/mnt/usb` integration tests and the PyInstaller build) |
| `.venv/bin/python -m app.cli --help` | all commands listed (unchanged) |

## Next

`TASK-132` (codify the index BPM rules) — `sync_playlists` already applies the
first-beat-tempo rule for tracks it writes a fresh grid for; TASK-132 is about
the ~70 already-wrong constant-tempo rows this pass never touches.
