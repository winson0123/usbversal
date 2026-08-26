# Current Task

**Status:** `idle`
**Task ID:** none
**Last updated:** 2026-08-26

---

## Last Completed

| Field | Value |
|-------|-------|
| Task ID | `TASK-133` |
| Objective | Prove, with a regression test, that writing our own GEOB frames never disturbs a frame belonging to another tool (Mixed In Key, Sound Forge) |
| Completed | 2026-08-26 |

### Scope

Files touched:

- `tests/test_never_clobber.py` (new) — builds a synthetic ID3v2.4 MP3
  carrying Mixed In Key's real frame names (`Key`, `Energy`, `CuePoints`,
  unprefixed `BeatGrid`) plus a placeholder for Sound Forge's undocumented
  frame, alongside our own `Serato BeatGrid`/`Serato Markers2`. Four tests:
  foreign frames survive a beatgrid write, survive a cue write, survive
  removing one of our own frames, and a write with no room to grow is refused
  rather than evicting a foreign frame to make space
- `docs/HANDOFF.md`, `docs/tasks/backlog.md`, `docs/state/*.json`

### Design decisions

- **No production code changed.** `write_geob` already only rebuilds frame
  descriptions named in `updates`/`remove_geob`/`remove_frames`; every other
  frame passes through the rebuild loop unchanged by construction. This task
  was specifically to prove that with a test, per HANDOFF.md ("nothing
  enforces that"), not to add a new runtime guard for something that already
  can't happen.
- **A synthetic MP3, not the WAV fixture.** The existing `Techno1.BEFORE.wav`
  fixture doesn't carry Mixed In Key or Sound Forge frames, and hand-building
  raw ID3v2.4 bytes is straightforward (same approach as `test_anlz.py`'s and
  `test_sync_playlists.py`'s synthetic-container builders). This incidentally
  exercises the MP3 tag path too, which `docs/tasks/backlog.md` still lists as
  untested (TASK-084) — not this task's goal, but free coverage.
- **Sound Forge's real frame name is undocumented anywhere in this repo**, so
  a placeholder (`"Unknown Vendor Tag"`) stands in for it. The guarantee has
  to hold for any frame we don't recognise, not only ones we can name, so a
  placeholder is the more honest test than guessing at a string.
- **The "refused, not evicted" case reuses the existing `padding < 0` check**
  in `write_geob` — confirms that safety net still holds with foreign frames
  present, and that the file is completely untouched on disk when it fires
  (the check runs before the temp file is ever written).

### Verification log

| Check | Result |
|-------|--------|
| `.venv/bin/ruff check .` | pass |
| `.venv/bin/ruff format --check .` | pass |
| `.venv/bin/pytest` | 173 passed, 3 skipped (no stick mounted; skips are the two `/mnt/usb` integration tests and the PyInstaller build) |
| `.venv/bin/python -m app.cli --help` | all commands listed (unchanged) |

## Next

Nothing left in the M10.5 "finish the analysis port" backlog block —
TASK-130 through TASK-134 (TASK-134 folded into TASK-126) are all done. The
next pending items are M11 TUI groundwork (TASK-201, 203, 204, 206) and the
older M8/M10 items (TASK-075, 076, 090); see `docs/tasks/backlog.md`. The one
thing HANDOFF.md still calls out as unfinished is re-validating
`sync_playlists`/`correct_index_bpm` against the real stick at `/mnt/usb`,
which needs the physical device rather than more code.
